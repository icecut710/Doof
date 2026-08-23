from __future__ import annotations

from pathlib import Path
from dataclasses import dataclass

import torch
import torch.nn.functional as F
from torch.amp import GradScaler, autocast
from tqdm import tqdm

from doof.model import DOOFTransformer
from doof.tokenizer import DOOFTokenizer


@dataclass
class TrainingConfig:
    data_path: str = "data/train.txt"
    checkpoint_dir: str = "checkpoints"

    epochs: int = 20
    batch_size: int = 8
    seq_len: int = 128

    learning_rate: float = 3e-4
    weight_decay: float = 0.01

    log_every: int = 10
    save_every: int = 100


class DOOFTrainer:
    def __init__(self, config: TrainingConfig):
        self.config = config

        self.device = torch.device(
            "cuda" if torch.cuda.is_available() else "cpu"
        )

        self.tokenizer = DOOFTokenizer()

        self.model = DOOFTransformer(
            vocab_size=self.tokenizer.vocab_size,
            max_seq_len=config.seq_len,
        ).to(self.device)

        self.optimizer = torch.optim.AdamW(
            self.model.parameters(),
            lr=config.learning_rate,
            weight_decay=config.weight_decay,
        )

        self.scaler = GradScaler(
            "cuda",
            enabled=self.device.type == "cuda",
        )

        Path(config.checkpoint_dir).mkdir(
            parents=True,
            exist_ok=True,
        )

    def load_data(self) -> torch.Tensor:
        text = Path(self.config.data_path).read_text(
            encoding="utf-8"
        )

        tokens = self.tokenizer.encode(text)

        return torch.tensor(
            tokens,
            dtype=torch.long,
        )

    def create_batches(self, tokens: torch.Tensor):
        seq_len = self.config.seq_len
        batch_size = self.config.batch_size

        usable = len(tokens) - seq_len - 1

        if usable <= 0:
            raise ValueError(
                "Dataset is too small for the configured sequence length."
            )

        starts = torch.randint(
            0,
            usable,
            (batch_size,),
        )

        x = torch.stack(
            [
                tokens[i : i + seq_len]
                for i in starts
            ]
        )

        y = torch.stack(
            [
                tokens[i + 1 : i + seq_len + 1]
                for i in starts
            ]
        )

        return x.to(self.device), y.to(self.device)

    def save_checkpoint(
        self,
        step: int,
        loss: float,
    ):
        checkpoint = {
            "model_state_dict": self.model.state_dict(),
            "optimizer_state_dict": self.optimizer.state_dict(),
            "step": step,
            "loss": loss,
            "config": self.config.__dict__,
            "model_config": {
                "vocab_size": self.tokenizer.vocab_size,
                "max_seq_len": self.config.seq_len,
                "d_model": self.model.d_model,
            },
        }

        path = (
            Path(self.config.checkpoint_dir)
            / f"doof_step_{step}.pt"
        )

        torch.save(checkpoint, path)

        print(f"\nCheckpoint saved: {path}")

    def train(self):
        tokens = self.load_data()

        print("================================")
        print("DOOF TRAINING")
        print("================================")
        print(f"Device: {self.device}")
        print(f"Tokens: {len(tokens):,}")
        print(
            f"Parameters: "
            f"{sum(p.numel() for p in self.model.parameters()):,}"
        )

        step = 0

        for epoch in range(self.config.epochs):
            progress = tqdm(
                range(100),
                desc=f"Epoch {epoch + 1}/{self.config.epochs}",
            )

            for _ in progress:
                self.model.train()

                x, y = self.create_batches(tokens)

                self.optimizer.zero_grad(
                    set_to_none=True
                )

                with autocast(
                    device_type=self.device.type,
                    dtype=torch.float16,
                    enabled=self.device.type == "cuda",
                ):
                    logits = self.model(x)

                    loss = F.cross_entropy(
                        logits.reshape(-1, logits.size(-1)),
                        y.reshape(-1),
                    )

                self.scaler.scale(loss).backward()

                self.scaler.unscale_(self.optimizer)

                torch.nn.utils.clip_grad_norm_(
                    self.model.parameters(),
                    1.0,
                )

                self.scaler.step(self.optimizer)
                self.scaler.update()

                step += 1

                progress.set_postfix(
                    loss=f"{loss.item():.4f}"
                )

                if step % self.config.save_every == 0:
                    self.save_checkpoint(
                        step,
                        loss.item(),
                    )

            self.save_checkpoint(
                step,
                loss.item(),
            )

        print("\nDOOF training complete.")