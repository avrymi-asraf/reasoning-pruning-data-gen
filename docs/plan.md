# **Reasoning Pruning Plan**

Project: `reasoning-pruning`

## **Core Idea**

Train a model on its own pruned and optimized reasoning path.

The core loop is simple: take a generator model version `G`, use it to create a reasoning trajectory, prune that trajectory with another LLM `D`, create a pruning-transition dataset (`PT dataset`), and then train the same model on that optimized data.

The goal is not to train the model to rewrite a full verbose answer into a short answer. The goal is to teach the local transition:

question \+ useful prefix \-\> next useful step after pruning

If a reasoning trace contains sentences that are unnecessary, redundant, or locally skippable, the model should learn to move directly from the useful prefix to the next useful step. Across many examples, the model learns to skip unnecessary reasoning sentences during generation instead of producing them and then compressing them afterward.

We believe this type of data can help the model avoid some of the common problems of fine-tuning, because it trains a concrete continuation behavior rather than only training final-answer style.

## **Intuitive Process**

Assume we have:  
$G$ — the generator model version we want to train.  
$D$ — the decision model that identifies removable reasoning units.  
$q$ — the original input question or task.

We run the generator on the input:  
$$  
G(q)  
$$

and receive a sequence of reasoning sentences or reasoning units:  
$$  
(s\_1, s\_2, ..., s\_{k-1}, s\_k, s\_{k+1}, ..., s\_n)  
$$

The goal is to find the first sentence, or first short span of sentences, that can be skipped without harming the reasoning process.

For example, suppose the generated reasoning is:  
$$  
A \\rightarrow B \\rightarrow C \\rightarrow D  
$$

and the decision model determines that $C$ is unnecessary. We do not merely save the full pair:  
$$  
A,B,C,D \\rightarrow A,B,D  
$$

That would describe the pruning result, but it is not the clearest training signal.

Instead, we create a next-step training example:  
$$  
x \= (q, A, B)  
$$  
$$  
y \= D  
$$

The model is trained to continue from the useful prefix directly to the next useful sentence. In other words, when the model reaches $A,B$, it should learn that it can skip $C$ and continue with $D$.

This distinction is central to the project:  
The dataset is not primarily a dataset of “original output → shortened output.”  
It is a pruning-transition dataset: “reasoning prefix → next useful reasoning step after pruning.”

The process can continue iteratively. After creating the first pruned continuation, we feed the pruned prefix back into the generator. The generator produces a new continuation from the already-pruned state. Then the decision model finds the next removable unit, and we create another training example at a deeper pruning level.

This means that a single original question can produce several training examples, each one representing a deeper level of reasoning compression.

This is a continuous process: we take a model, create a PT dataset, train on that dataset, save the updated model, and then run the next round. In the next round, the updated model can be used to create a new PT dataset, train again, and continue the loop.

## **System Structure and Repo Connections**

The project is split into cooperating repositories with file-based handoffs. Repositories do not import Python modules from each other.

`reasoning-pruning-data-gen`

* Creates versioned PT datasets.  
* Owns research-heavy data acquisition, decision modeling, and data-generation experiments.  
* Owns how PT datasets are generated. It does not train models.  
* Consumes a config and initializes the dataset-creation process from it.  
* Uses `G`, a Hugging Face model repo revision stored locally in `reasoning-pruning-models`, to generate reasoning traces, and uses `D` through LiteLLM to prune them.  
* Updates the dataset artifact store with artifacts and metadata stored locally in `reasoning-pruning-datasets`.  
* Can run the creation process locally or remotely, for example as a Hugging Face job. `G` can also run locally or on cloud compute.

`reasoning-pruning-train`

* Trains models on an existing PT dataset.  
* Consumes a PT dataset, a model, and a training config.  
* Fine-tunes models on pruning-transition examples.  
* Runs training as a Hugging Face job and uses W\&B to display training metrics.  
* Owns the fine-tuning implementation and training experiments. It does not decide how to generate the PT dataset.  
* This is an R\&D repo. We need to experiment constantly, document the experiments, and find the best fine-tuning setup for this type of data.  
* Writes checkpoints, training metrics, and `run_metadata.json`.

`reasoning-pruning-experiments`

* Owns the experiment loop: choose, train, evaluate, decide, and save.  
* Does not implement data generation or training itself. It coordinates the other repos.  
* Chooses benchmark datasets for local or cloud evaluation.  
* Calls `reasoning-pruning-train` with a selected model, PT dataset, training config, and train branch.  
* Evaluates the resulting checkpoint, decides whether it is good enough to become a new model version, and writes a clear log describing this step in the model chain.

## **Artifact Stores**

* `reasoning-pruning-datasets`: local repo containing Hugging Face dataset repos.  
* `reasoning-pruning-models`: local repo containing Hugging Face model repos.

Each dataset repo should expose a clear dataset version or revision.

Each model repo inside `reasoning-pruning-models` should be a Hugging Face model repo, not just a loose checkpoint folder. The model repo should contain the model artifacts and a clear model card or metadata file that documents the full training chain that led to the current state of the model. `reasoning-pruning-experiments` is responsible for updating this chain when a new trained checkpoint is accepted as a new model version.

## **All Process**

Choose a model and create a new Hugging Face model repo for it inside `reasoning-pruning-models`.

Choose the initial dataset. Use `reasoning-pruning-data-gen` to create a new PT dataset connected to this specific model version. Save it as a Hugging Face dataset repo.

The train loop stops when the evaluation is good enough:

`reasoning-pruning-experiments` runs training for this model on the corresponding dataset by calling `reasoning-pruning-train` with a specific config.

`reasoning-pruning-experiments` evaluates the trained checkpoint.

If the checkpoint is good enough, it becomes a new version or commit inside the same Hugging Face model repo. The model repo must also be updated with documentation that describes the training step that produced this version.

Then we can create a new version of the PT dataset using this updated model version.

This is the operating model we are aiming for. Since this is research and development, we will probably move freely between the steps until we find settings that work well enough.

## **reasoning-pruning-data-gen**

It should collect or generate questions `q`, load `G` from a Hugging Face model repo, ask `G` to produce reasoning traces, use `D` to optimize those traces through pruning, and preserve enough metadata to reproduce the source dataset, generator model version, prompt, and decision configuration. Dataset versions should be explicit and immutable once used for training.

The output is not just a set of examples. The output is a versioned Hugging Face dataset repo tied to a specific source dataset revision, generator model revision, decision model, decision prompt, and pruning config. These details should live in the dataset-level config or metadata, so each JSONL row can stay minimal.

The PT data should be saved as a Hugging Face dataset repo.

## **Decision Component**

`D` decides whether a reasoning unit or span is safely removable.

`D` is an LLM accessed through the LiteLLM interface. Given the reasoning process produced by `G`, it finds the first sentence, or first short span, that can be skipped without damaging the reasoning chain.

`D` must not rewrite the reasoning trace, summarize it, or rank all sentences by importance. Its job is narrower: identify the first safely removable unit or span, and return enough information for the data-generation code to construct the next-step training example.

The data-generation layer is the execution layer of `reasoning-pruning-data-gen`. It is responsible for turning the idea into concrete training examples.

The key object is a pruning-transition example:  
$$  
e \= {x, y, depth}  
$$

where:  
$x$ is the original input plus the useful reasoning prefix.  
$y$ is the next useful reasoning sentence after the skipped sentence or skipped span.  
$depth$ is the pruning depth: how many pruning iterations were used to reach this example.

## **First pruning step**

Given the original question $q$, run:  
$$  
G(q)  
$$

and receive:  
$$  
(s\_1, s\_2, ..., s\_{k-1}, s\_k, s\_{k+1}, ..., s\_n)  
$$

Now run the decision model:  
$$  
D(q, (s\_1, s\_2, ..., s\_n))  
$$

Assume $D$ decides that $s\_k$ is unnecessary.

Then the training example is:  
$$  
e\_1 \= {x: (q, s\_1, s\_2, ..., s\_{k-1}),\\ y: s\_{k+1},\\ depth: 1}  
$$

This is a level-1 pruning-transition example.

Its meaning is simple:  
After the model has seen the original question and the useful prefix $s\_1, ..., s\_{k-1}$, it should learn to continue directly with $s\_{k+1}$ instead of producing $s\_k$.

If the removable part is a span rather than a single sentence, for example:  
$$  
(s\_k, s\_{k+1}, ..., s\_l)  
$$

then the example becomes:  
$$  
e\_1 \= {x: (q, s\_1, ..., s\_{k-1}),\\ y: s\_{l+1},\\ depth: 1}  
$$

So the model learns to jump from the prefix directly to the next useful sentence after the skipped span.

## **Second pruning step**

The first example can also become the starting point for another generation step.

After pruning $s\_k$, we create a pruned context:  
$$  
(q, s\_1, s\_2, ..., s\_{k-1}, s\_{k+1})  
$$

Now we feed this pruned context back into the generator:  
$$  
G(q, s\_1, s\_2, ..., s\_{k-1}, s\_{k+1})  
$$

The generator produces a new continuation:  
$$  
(h\_1, h\_2, ..., h\_{j-1}, h\_j, h\_{j+1}, ..., h\_m)  
$$

This continuation is expected to continue the already-pruned reasoning path.

Now we run the decision model again:  
$$  
D((q, s\_1, ..., s\_{k-1}, s\_{k+1}), (h\_1, h\_2, ..., h\_m))  
$$

Assume $D$ decides that $h\_j$ is unnecessary.

Then we create a second-depth example:  
$$  
e\_2 \= {x: (q, s\_1, ..., s\_{k-1}, s\_{k+1}, h\_1, ..., h\_{j-1}),\\ y: h\_{j+1},\\ depth: 2}  
$$

This is a level-2 pruning-transition example. It was created after two pruning iterations: first skipping $s\_k$, and then skipping $h\_j$ in the continuation generated from the already-pruned context.

## **General iterative process**

The same process can continue repeatedly:

Start with an input question $q$.

Generate reasoning with `G`.

Use `D` to find the first safely removable sentence or span.

Convert that pruning decision into a training example:  
$$  
x \= \\text{question \+ useful prefix}  
$$  
$$  
y \= \\text{next useful sentence after the skipped unit}  
$$

Save the example with its depth.

Feed the pruned context back into `G`.

Repeat until `D` decides that no more safe pruning is possible or that the answer is already good enough.

This means that from one question we expect to create several pruned examples:  
$$  
e\_1, e\_2, e\_3, ..., e\_t  
$$

Each example represents a different depth of pruning and a different point in the compressed reasoning path.

model version G \-\> generate \-\> find first safe skip \-\> write next-step example \-\> continue from pruned context

## **JSON Schema**

Each JSONL row should stay compact. Reproducibility should come from the row `id`, the `decision` reference, and the dataset-level config or metadata. The row itself should not become a heavy audit object.

{  
  "id": "dataset\_version/example\_id/depth",  
  "question": "...",  
  "input\_x": "question plus useful prefix",  
  "target\_y": "next useful step after pruning",  
  "depth": 0,  
  "decision": {  
    "config": "...",  
    "commit": "..."  
  }  
}

## **Create PT dataset**

Given a source dataset, initially only from Hugging Face, and a config file, we can run the full process that converts the source dataset into a PT dataset as explained above.

The config file needs to contain:

Model `G`: the Hugging Face model used as the generator, including its exact version or commit.  
Model `D`: the decision model.  
Prompt for model `D`: text or a path to a prompt file, including the prompt version or commit.  
Dataset: the source dataset, including its exact revision when available.  
Partition: how to split the data into train, test, and eval.  
Amount: how many data entries to convert.  
Any other config needed for reproducibility.

Commands:

`try-dataset`: Try the PT dataset creation process on a small part of a source dataset. This tool helps us decide whether the dataset is worth converting fully or partially.

`convert-dataset`: Given a dataset and config, convert the full dataset or part of it and update the dataset version.

We also need a small portal or viewer where we can inspect the generated results directly for one or two examples.

## **reasoning-pruning-train**

Training belongs to `reasoning-pruning-train`.

Training should run as Hugging Face jobs, with W\&B used to visualize metrics.

Every training run should contain:

* Dataset and version.  
* Number of examples used for training.  
* Model and version.  
* Training branch and commit.  
* Training method.  
* Every parameter of the training method.

Fine-tuning should optimize the transition behavior:

(q \+ useful prefix) \-\> next useful step after pruning

The model should not merely learn to summarize. It should learn to continue reasoning as if the removable span was never generated.

Training outputs should include:

* Checkpoint artifact or checkpoint reference.  
* Training metrics.  
* `run_metadata.json` for downstream evaluation and chain tracking.

Commands:

`train`: Given a PT dataset, model, and training config, train the model and save the checkpoint.

## **Evaluation & Management**

This repo, `reasoning-pruning-experiments`, is the management and evaluation layer.

It owns the experiment loop. It does not implement training itself; it calls the train repo, evaluates the produced checkpoint, decides whether the checkpoint should become a new model version, and records the full checkpoint lineage.

Its responsibilities are:

* Evaluate checkpoints trained by `reasoning-pruning-train`.  
* Choose benchmark datasets that can run locally or as cloud/Hugging Face jobs.  
* Check whether fine-tuning improves pruning behavior.  
* Check whether fine-tuning damages general model capability.  
* Manage the training and evaluation process as the entrypoint for experiments.  
* Record each checkpoint chain clearly.

For every accepted model version, mostly produced from a trained checkpoint, update the relevant Hugging Face model repo with:

* Model version or commit reference.  
* Parent version from the same Hugging Face model repo, or base model.  
* Dataset and version, including the exact dataset config.  
* Training config.  
* Training metrics copied from W\&B.  
* Evaluation metrics, when evaluation is run.  
* A short description of why this version was accepted or kept.

Evaluation should eventually cover both pruning-specific behavior and broad capability retention. Some runs may be small local smoke tests; larger runs may use cloud compute and cloud-hosted artifacts.

Evaluate config:

Train config: train config path for `train-and-evaluate`.

Evaluate config should contain:

Model: model and version.  
Evaluation: list of evaluations to run.  
Commit: whether to commit the model directly after the evaluation or not.

Commands:

`evaluate`: Given a config, run evaluation on a model and display the results.

`train-and-evaluate`: Run training through `reasoning-pruning-train`, evaluate the resulting checkpoint, and if accepted, record the result as a new documented version in the relevant Hugging Face model repo.

