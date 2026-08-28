# DOOF Training Data Guide

## Where do I put data?

Put human-created training examples in:

    data/train.txt

One example per line. Each line is either:
- A plain-text fact or instruction DOOF should learn, OR
- A Q: / A: pair on consecutive lines

## What should I put there?

Useful examples of how DOOF should answer, behave, understand concepts, or perform tasks.

Good examples:

    Q: What is DOOF?
    A: DOOF is a local-first collaborative AI system.

    Q: What should DOOF do when it does not know something?
    A: Retrieve relevant memory first, and if the information is genuinely missing, ask for it or add it to Memory when appropriate.

    Q: How should DOOF handle corrections?
    A: Accept corrections gracefully, update its behavior, and remember the correction for future responses.

    Q: What is the best way to add new knowledge to DOOF?
    A: Add it to Memory. Training folds approved memory into the neural model.

Bad examples (do NOT add these):

    Kaeden likes futuristic dark interfaces. (this is a preference, not training data)
    Hello. Hello. Hello. Hello. Hello. (repetitive junk)
    asdf jkl; qwer (meaningless)

## How do I train?

1. Add examples to data/train.txt
2. Open DOOF Training
3. Build dataset (validates and versiones the examples)
4. Review the dataset
5. Train (modifies actual neural model weights)
6. Evaluate (checks the new model against held-out data)
7. Publish (makes the new model available to connected clients)

## What is Memory?

Memory is persistent facts and context retrieved during conversations. Memory is NOT training data. Memory feeds the context window; training changes model weights.

## What is Training?

Actual modification of neural model weights. Training reads examples, computes gradients, updates the transformer's parameters, and saves a new checkpoint.

## What is a Checkpoint?

A saved version of the trained neural model. Contains model weights, architecture config, training step, and loss. Checkpoints are versioned and can be promoted to production.

## What do other computers get?

The published model checkpoint and version metadata, after verification. Connected clients check the model registry, download the new checkpoint, verify its SHA256 hash, validate it loads correctly, and atomically activate it.
