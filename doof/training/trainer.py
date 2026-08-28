from __future__ import annotations

import gc
import os
from dataclasses import dataclass
from pathlib import Path

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
    def __init__(
        self,
        config: TrainingConfig,
        tokenizer: object | None = None,
    ):
        self.config = config

        self.device = torch.device(
            "cuda" if torch.cuda.is_available() else "cpu"
        )

        self.tokenizer = tokenizer or DOOFTokenizer()

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

        # Save tokenizer with the checkpoint dir so it travels with checkpoints
        self.tokenizer.save_for_checkpoint(config.checkpoint_dir)

    def load_data(self) -> torch.Tensor:
        text = Path(self.config.data_path).read_text(encoding="utf-8")
        if not text.strip():
            raise ValueError(
                f"Training data file is empty: {self.config.data_path}"
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
        is_best: bool = False,
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
                "d_model": int(getattr(self.model, "d_model", 256)),
                # Read defensively: metadata only — works with any model class
                # the neural-model agent lands, as long as it's a torch Module.
                "n_heads": int(getattr(self.model, "n_heads", 8)),
                "n_layers": int(getattr(self.model, "n_layers", 6)),
                "tokenizer_version": getattr(self.tokenizer, "version", "bpe-1.0"),
            },
        }

        path = (
            Path(self.config.checkpoint_dir)
            / f"doof_step_{step}.pt"
        )

        torch.save(checkpoint, path)

        # Ensure tokenizer.json is always up-to-date
        self.tokenizer.save_for_checkpoint(self.config.checkpoint_dir)

        print(f"\nCheckpoint saved: {path}")

        if is_best:
            best_path = Path(self.config.checkpoint_dir) / "doof_best.pt"
            import shutil
            shutil.copy2(path, best_path)
            print(f"Best checkpoint copied to: {best_path}")

    def train(self, val_split: float = 0.1) -> dict[str, Any]:
        tokens = self.load_data()

        print("================================")
        print("DOOF TRAINING")
        print("================================")
        print(f"Device: {self.device}")
        print(f"Tokens: {len(tokens):,}")
        print(f"Vocab size: {self.tokenizer.vocab_size}")
        print(
            f"Parameters: "
            f"{sum(p.numel() for p in self.model.parameters()):,}"
        )

        # Build validation split from the tokens
        total_tokens = len(tokens)
        val_size = int(total_tokens * val_split)
        train_tokens = tokens[:-val_size]
        val_tokens = tokens[-val_size:]

        # Create train/val batches
        train_batches = 0
        val_batches = 0
        train_losses: list[float] = []
        val_losses: list[float] = []

        step = 0
        best_val_loss = float("inf")
        epochs_without_improvement = 0
        max_epochs_without_improvement = 5  # early stopping patience

        for epoch in range(self.config.epochs):
            if _stop.is_set() if '_stop' in dir() else False:
                break

            progress = tqdm(
                range(100),
                desc=f"Epoch {epoch + 1}/{self.config.epochs}",
            )

            for _ in progress:
                self.model.train()

                x, y = self.create_batches(train_tokens)

                self.optimizer.zero_grad(set_to_none=True)

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
                loss_val = float(loss.item())
                train_losses.append(loss_val)

                progress.set_postfix(loss=f"{loss_val:.4f}")

                if step % self.config.save_every == 0:
                    # Evaluate on validation set
                    val_loss = self._validate(val_tokens)
                    val_losses.append(val_loss)

                    # Check for improvement
                    if val_loss < best_val_loss:
                        best_val_loss = val_loss
                        epochs_without_improvement = 0
                        self.save_checkpoint(
                            step,
                            loss_val,
                            is_best=True,
                        )
                    else:
                        epochs_without_improvement += 1

                    # Early stopping
                    if epochs_without_improvement >= max_epochs_without_improvement:
                        print(
                            f"Early stopping at step {step} "
                            f"(no val loss improvement for "
                            f"{max_epochs_without_improvement} epochs)"
                        )
                        break

                    # Log progress
                    print(
                        f"Step {step}: "
                        f"train loss {loss_val:.4f} | "
                        f"val loss {val_loss:.4f} | "
                        f"best val {best_val_loss:.4f}"
                    )

            # End of epoch - save checkpoint
            self.save_checkpoint(
                step,
                train_losses[-1] if train_losses else 0.0,
            )

        # Final evaluation
        final_val_loss = self._validate(val_tokens) if val_losses else None

        print(f"\nDOOF training complete.")
        print(f"Best validation loss: {best_val_loss:.4f}")
        if final_val_loss is not None:
            print(f"Final validation loss: {final_val_loss:.4f}")

        # Generate text from the trained model to verify learning
        self.model.eval()
        with torch.no_grad():
            sample_ids = torch.randint(
                0, self.tokenizer.vocab_size, (1, 4), dtype=torch.long, device=self.device
            )
            prompt_len = sample_ids.shape[1]
            for _ in range(10):
                ctx = sample_ids[:, -self.config.seq_len:]
                logits = self.model(ctx)
                next_logits = logits[:, -1, :] / 0.8
                probs = torch.softmax(next_logits, dim=-1)
                next_tok = torch.multinomial(probs, num_samples=1)
                sample_ids = torch.cat([sample_ids, next_tok], dim=1)
            gen_ids = sample_ids[0].tolist()[prompt_len:]
            gen_text = self.tokenizer.decode(gen_ids)
            print(f"Sample generated text: {gen_text}")

        return {
            "step": step,
            "best_val_loss": best_val_loss,
            "final_val_loss": final_val_loss,
            "train_losses": train_losses,
            "val_losses": val_losses,
            "epochs_trained": epoch + 1,
        }

    def _validate(self, val_tokens: torch.Tensor) -> float:
        """Run one validation epoch and return average validation loss."""
        self.model.eval()

        seq_len = self.config.seq_len
        usable = len(val_tokens) - seq_len - 1
        if usable <= 0:
            return float("inf")

        # Use all available validation positions (up to 50 batches for speed)
        n_batches = min(50, usable)
        starts = torch.linspace(0, usable - 1, n_batches, dtype=torch.long)

        total_loss = 0.0
        total_batches = 0

        with torch.no_grad():
            for s in starts:
                x = val_tokens[s : s + seq_len].unsqueeze(0)
                y = val_tokens[s + 1 : s + seq_len + 1].unsqueeze(0)
                x = x.to(self.device)
                y = y.to(self.device)

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
                total_loss += float(loss.item())
                total_batches += 1

        return total_loss / total_batches if total_batches > 0 else float("inf")

    def cleanup(self) -> None:
        """Release model, optimizer, and scaler from memory after training."""
        self.model.cpu()
        del self.model
        del self.optimizer
        del self.scaler
        self.optimizer = None
        self.scaler = None
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()