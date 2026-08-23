import time
from doof.api import run_train, _train, _stop

print("Starting training dry run...")
run_train(epochs=1)
while _train["running"]:
    print(f"[{_train['step']}] Loss: {_train['loss']}")
    time.sleep(1)

print("Training finished.")
print("Final state:", _train)
