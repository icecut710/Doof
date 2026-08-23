from doof.training import DOOFTrainer, TrainingConfig


def main():
    config = TrainingConfig(
        data_path="data/train.txt",
        checkpoint_dir="checkpoints",
        epochs=5,
        batch_size=8,
        seq_len=128,
        learning_rate=3e-4,
    )

    trainer = DOOFTrainer(config)
    trainer.train()


if __name__ == "__main__":
    main()