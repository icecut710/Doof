from __future__ import annotations

from pathlib import Path

import torch

from doof.model import DOOFTransformer
from doof.tokenizer import DOOFTokenizer


class DOOFInference:
    def __init__(self, checkpoint_path: str):
        self.device = torch.device(
            "cuda" if torch.cuda.is_available() else "cpu"
        )

        self.tokenizer = DOOFTokenizer()

        checkpoint_file = Path(checkpoint_path)

        if not checkpoint_file.exists():
            raise FileNotFoundError(
                f"Checkpoint not found: {checkpoint_file}"
            )

        checkpoint = torch.load(
            checkpoint_file,
            map_location=self.device,
            weights_only=False,
        )

        self.step = checkpoint.get("step", 0)
        self.loss = checkpoint.get("loss")

        model_config = checkpoint.get("model_config", {})

        self.model = DOOFTransformer(
            vocab_size=model_config.get(
                "vocab_size",
                self.tokenizer.vocab_size,
            ),
            max_seq_len=model_config.get(
                "max_seq_len",
                128,
            ),
            d_model=model_config.get(
                "d_model",
                256,
            ),
        ).to(self.device)

        self.model.load_state_dict(
            checkpoint["model_state_dict"]
        )

        self.model.eval()

    @torch.no_grad()
    def generate(
        self,
        prompt: str,
        max_new_tokens: int = 100,
        temperature: float = 0.8,
    ) -> str:

        if not prompt.strip():
            return ""

        tokens = self.tokenizer.encode(
            prompt,
            add_bos=True,
            add_eos=False,
        )

        input_ids = torch.tensor(
            [tokens],
            dtype=torch.long,
            device=self.device,
        )

        for _ in range(max_new_tokens):
            context = input_ids[
                :, -self.model.max_seq_len:
            ]

            logits = self.model(context)

            next_token_logits = logits[:, -1, :]

            temperature = max(
                float(temperature),
                1e-5,
            )

            next_token_logits = (
                next_token_logits / temperature
            )

            probabilities = torch.softmax(
                next_token_logits,
                dim=-1,
            )

            next_token = torch.multinomial(
                probabilities,
                num_samples=1,
            )

            input_ids = torch.cat(
                [input_ids, next_token],
                dim=1,
            )

            if (
                next_token.item()
                == self.tokenizer.EOS
            ):
                break

        return self.tokenizer.decode(
            input_ids[0].tolist()
        )