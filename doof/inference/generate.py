from __future__ import annotations

from pathlib import Path


class DOOFInference:
    def __init__(self, checkpoint_path: str):
        from doof.runtime import import_torch, resolve_device, torch_error

        torch = import_torch()
        if torch is None:
            raise RuntimeError(torch_error() or "torch unavailable")

        from doof.model import DOOFTransformer
        from doof.tokenizer import DOOFTokenizer, LegacyTokenizer

        self._torch = torch
        device_str, device_label = resolve_device(torch)
        self.device = torch.device(device_str)
        self.device_label = device_label

        checkpoint_file = Path(checkpoint_path)
        if not checkpoint_file.exists():
            raise FileNotFoundError(f"Checkpoint not found: {checkpoint_file}")

        checkpoint = torch.load(checkpoint_file, map_location=self.device, weights_only=False)
        self.step = checkpoint.get("step", 0)
        self.loss = checkpoint.get("loss")
        model_config = checkpoint.get("model_config", {})
        ckpt_vocab_size = model_config.get("vocab_size", 1024)

        # Try to load tokenizer that was saved with this checkpoint
        ckpt_dir = checkpoint_file.parent
        saved_tok = DOOFTokenizer.load_from_checkpoint(ckpt_dir)

        if saved_tok is not None:
            # Verify the saved tokenizer matches the checkpoint's vocab_size
            if saved_tok.vocab_size != ckpt_vocab_size:
                raise ValueError(
                    f"Tokenizer vocab_size mismatch: checkpoint has vocab_size={ckpt_vocab_size}, "
                    f"but saved tokenizer has vocab_size={saved_tok.vocab_size}. "
                    f"This checkpoint was trained with a different tokenizer. "
                    f"Retrain with the current tokenizer or provide the matching tokenizer.json."
                )
            self.tokenizer = saved_tok
        elif ckpt_vocab_size == LegacyTokenizer.VOCAB_SIZE:
            # Legacy checkpoint (vocab_size=259) → use the legacy byte tokenizer
            self.tokenizer = LegacyTokenizer()
        else:
            # New checkpoint without tokenizer.json — cannot proceed safely
            raise ValueError(
                f"Checkpoint specifies vocab_size={ckpt_vocab_size} but no tokenizer.json "
                f"was found in {ckpt_dir}. A tokenizer.json file must accompany the checkpoint. "
                f"Retrain to generate one, or provide it manually."
            )

        self.model = DOOFTransformer(
            vocab_size=ckpt_vocab_size,
            max_seq_len=model_config.get("max_seq_len", 128),
            d_model=model_config.get("d_model", 256),
            n_heads=model_config.get("n_heads", 8),
            n_layers=model_config.get("n_layers", 6),
        ).to(self.device)
        self.model.load_state_dict(checkpoint["model_state_dict"])
        self.model.eval()
        self.checkpoint_path = str(checkpoint_file)
        self.max_seq_len = self.model.max_seq_len

    def generate(
        self,
        prompt: str,
        max_new_tokens: int = 100,
        temperature: float = 0.8,
        top_k: int = 50,
    ) -> str:
        if not prompt.strip():
            return ""

        torch = self._torch
        tokens = self.tokenizer.encode(prompt, add_bos=True, add_eos=False)
        prompt_len = len(tokens)
        input_ids = torch.tensor([tokens], dtype=torch.long, device=self.device)

        with torch.no_grad():
            for _ in range(max_new_tokens):
                context = input_ids[:, -self.model.max_seq_len :]
                logits = self.model(context)
                next_token_logits = logits[:, -1, :] / max(float(temperature), 1e-5)

                if top_k and top_k > 0:
                    v, _ = torch.topk(next_token_logits, min(top_k, next_token_logits.size(-1)))
                    next_token_logits[next_token_logits < v[:, [-1]]] = float("-inf")

                probabilities = torch.softmax(next_token_logits, dim=-1)
                next_token = torch.multinomial(probabilities, num_samples=1)
                input_ids = torch.cat([input_ids, next_token], dim=1)

                if next_token.item() == self.tokenizer.EOS:
                    break

        generated = input_ids[0].tolist()[prompt_len:]
        return self.tokenizer.decode(generated).strip()
