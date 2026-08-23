from doof.inference import DOOFInference


def main():
    doof = DOOFInference(
        "checkpoints/doof_step_500.pt"
    )

    print("🧠 DOOF is loaded.")
    print("Type 'exit' to quit.\n")

    while True:
        prompt = input("You: ")

        if prompt.lower() == "exit":
            break

        response = doof.generate(
            prompt,
            max_new_tokens=80,
            temperature=0.7,
        )

        print(f"DOOF: {response}\n")


if __name__ == "__main__":
    main()