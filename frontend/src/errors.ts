/** Turn API / runtime failures into something a human can read. */

export type FriendlyError = {
  title: string;
  body: string;
  action: string;
  technical?: string;
};

const TORCH = /torchdistribute|torch\.distributed|no module named ['"]?torch/i;

export function friendlyError(raw: unknown): FriendlyError {
  const msg = raw instanceof Error ? raw.message : String(raw ?? "");
  const technical = msg;
  if (TORCH.test(msg)) {
    return {
      title: "The local brain failed to start.",
      body: "DOOF switched to its backup brain.",
      action: "You can keep chatting. A friend with a stronger PC can share compute.",
      technical,
    };
  }
  if (/failed to fetch|networkerror|econnrefused/i.test(msg)) {
    return {
      title: "Lost in the desert",
      body: "Couldn't reach the DOOF brain.",
      action: "Check that this machine is running, or join an existing brain.",
      technical,
    };
  }
  if (/traceback|modulenotfounderror|exception in/i.test(msg)) {
    return {
      title: "Something spilled in the kitchen",
      body: "DOOF caught the error and stayed open.",
      action: "Try again. Technical details are available if you need them.",
      technical,
    };
  }
  return {
    title: msg.length > 80 ? "Something spilled in the kitchen" : msg || "Request failed",
    body: "DOOF stayed open.",
    action: "Try again in a moment.",
    technical,
  };
}
