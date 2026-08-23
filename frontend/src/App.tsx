import { useState } from "react";

type Page =
  | "chat"
  | "knowledge"
  | "training"
  | "models"
  | "hardware"
  | "settings";

type Message = {
  role: "user" | "doof";
  text: string;
};

const pages: {
  id: Page;
  label: string;
  icon: string;
  section: string;
}[] = [
  { id: "chat", label: "Chat", icon: "◆", section: "DOOF" },
  { id: "knowledge", label: "Knowledge", icon: "◇", section: "DOOF" },
  { id: "training", label: "Training", icon: "↯", section: "LEARN" },
  { id: "models", label: "Models", icon: "◈", section: "SYSTEM" },
  { id: "hardware", label: "Hardware", icon: "▣", section: "SYSTEM" },
  { id: "settings", label: "Settings", icon: "⚙", section: "SYSTEM" },
];

const sections = ["DOOF", "LEARN", "SYSTEM"];

function App() {
  const [page, setPage] = useState<Page>("chat");
  const [message, setMessage] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);

  const sendMessage = () => {
    const text = message.trim();

    if (!text) return;

    setMessages((current) => [
      ...current,
      {
        role: "user",
        text,
      },
    ]);

    setMessage("");

    setTimeout(() => {
      setMessages((current) => [
        ...current,
        {
          role: "doof",
          text: "DOOF is thinking...",
        },
      ]);
    }, 150);
  };

  return (
    <div className="relative h-screen w-screen overflow-hidden bg-[#030304] text-zinc-300 selection:bg-violet-500/20">
      {/* ===================================================== */}
      {/* BACKGROUND                                             */}
      {/* ===================================================== */}

      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        {/* Mr Naddaf watermark */}
        <img
          src="/mrnaddaf.png"
          alt=""
          className="
            absolute
            right-[-10%]
            top-[-3%]
            h-[110%]
            w-[58%]
            object-contain
            object-right
            opacity-[0.045]
            grayscale
            mix-blend-screen
          "
        />

        {/* subtle center glow */}
        <div
          className="
            absolute
            left-[45%]
            top-[40%]
            h-[500px]
            w-[500px]
            -translate-x-1/2
            -translate-y-1/2
            rounded-full
            bg-violet-600/[0.025]
            blur-[140px]
          "
        />

        {/* darkness gradient */}
        <div
          className="
            absolute
            inset-0
            bg-[linear-gradient(90deg,#030304_0%,#030304_45%,rgba(3,3,4,.72)_100%)]
          "
        />

        {/* extremely subtle vignette */}
        <div
          className="
            absolute
            inset-0
            bg-[radial-gradient(circle_at_center,transparent_25%,rgba(0,0,0,.32)_100%)]
          "
        />
      </div>

      {/* ===================================================== */}
      {/* APP                                                    */}
      {/* ===================================================== */}

      <div className="relative flex h-full min-h-0">
        {/* =================================================== */}
        {/* SIDEBAR                                               */}
        {/* =================================================== */}

        <aside
          className="
            flex
            w-[168px]
            shrink-0
            flex-col
            border-r
            border-white/[0.045]
            bg-[#050506]/95
            px-2.5
            py-3
          "
        >
          {/* Brand */}

          <div className="mb-7 px-2">
            <div className="flex items-center gap-2">
              <div
                className="
                  flex
                  h-[22px]
                  w-[22px]
                  items-center
                  justify-center
                  rounded-[6px]
                  border
                  border-violet-400/15
                  bg-violet-500/[0.055]
                  text-[9px]
                  font-bold
                  text-violet-400
                "
              >
                D
              </div>

              <span className="text-[13px] font-semibold tracking-[-0.03em] text-zinc-200">
                DOOF
              </span>
            </div>

            <div className="mt-1 pl-[30px] text-[7px] uppercase tracking-[0.17em] text-zinc-700">
              Local intelligence
            </div>
          </div>

          {/* Navigation */}

          <nav className="space-y-4">
            {sections.map((section) => (
              <div key={section}>
                <div className="mb-1 px-2 text-[7px] font-semibold tracking-[0.18em] text-zinc-800">
                  {section}
                </div>

                <div className="space-y-[2px]">
                  {pages
                    .filter((item) => item.section === section)
                    .map((item) => {
                      const active = page === item.id;

                      return (
                        <button
                          key={item.id}
                          onClick={() => setPage(item.id)}
                          className={`
                            group
                            flex
                            h-[29px]
                            w-full
                            items-center
                            gap-2
                            rounded-[6px]
                            px-2
                            text-left
                            text-[9px]
                            transition-all
                            duration-150
                            ${
                              active
                                ? "border border-white/[0.045] bg-white/[0.045] text-zinc-200"
                                : "border border-transparent text-zinc-600 hover:bg-white/[0.025] hover:text-zinc-400"
                            }
                          `}
                        >
                          <span
                            className={`
                              flex
                              w-3
                              justify-center
                              text-[8px]
                              ${
                                active
                                  ? "text-violet-400"
                                  : "text-zinc-800 group-hover:text-zinc-600"
                              }
                            `}
                          >
                            {item.icon}
                          </span>

                          {item.label}
                        </button>
                      );
                    })}
                </div>
              </div>
            ))}
          </nav>

          {/* Bottom system card */}

          <div className="mt-auto">
            <div
              className="
                rounded-[7px]
                border
                border-white/[0.045]
                bg-white/[0.012]
                px-2.5
                py-2
              "
            >
              <div className="flex items-center gap-1.5">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 shadow-[0_0_7px_rgba(52,211,153,.35)]" />

                <span className="text-[7px] font-medium uppercase tracking-[0.13em] text-emerald-500/80">
                  Online
                </span>
              </div>

              <div className="mt-1 text-[7px] text-zinc-700">
                CUDA · RTX 5060
              </div>

              <div className="mt-[2px] text-[7px] text-zinc-800">
                DOOF checkpoint 500
              </div>
            </div>
          </div>
        </aside>

        {/* =================================================== */}
        {/* MAIN                                                   */}
        {/* =================================================== */}

        <main className="flex min-w-0 flex-1 flex-col">
          {/* Top bar */}

          <header
            className="
              flex
              h-[42px]
              shrink-0
              items-center
              justify-between
              border-b
              border-white/[0.045]
              px-4
            "
          >
            <div className="flex items-center gap-2">
              <span className="text-[8px] uppercase tracking-[0.14em] text-zinc-700">
                DOOF
              </span>

              <span className="text-[8px] text-zinc-800">/</span>

              <span className="text-[8px] uppercase tracking-[0.12em] text-zinc-600">
                {page}
              </span>
            </div>

            <div className="flex items-center gap-1.5">
              <span className="h-1 w-1 rounded-full bg-emerald-400/80" />

              <span className="text-[7px] uppercase tracking-[0.13em] text-zinc-700">
                Local
              </span>
            </div>
          </header>

          {/* Page */}

          {page === "chat" ? (
            <Chat
              messages={messages}
              message={message}
              setMessage={setMessage}
              sendMessage={sendMessage}
            />
          ) : (
            <PlaceholderPage page={page} />
          )}
        </main>
      </div>
    </div>
  );
}

/* ============================================================= */
/* CHAT                                                           */
/* ============================================================= */

function Chat({
  messages,
  message,
  setMessage,
  sendMessage,
}: {
  messages: Message[];
  message: string;
  setMessage: (value: string) => void;
  sendMessage: () => void;
}) {
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      {/* Conversation */}

      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
        {messages.length === 0 ? (
          <EmptyChat />
        ) : (
          <div className="mx-auto w-full max-w-[680px] space-y-3">
            {messages.map((msg, index) => (
              <div
                key={`${msg.role}-${index}`}
                className={`flex ${
                  msg.role === "user"
                    ? "justify-end"
                    : "justify-start"
                }`}
              >
                <div
                  className={`
                    max-w-[70%]
                    rounded-[8px]
                    border
                    px-3
                    py-2
                    text-[10px]
                    leading-[1.6]
                    ${
                      msg.role === "user"
                        ? "border-violet-400/[0.09] bg-violet-500/[0.055] text-zinc-300"
                        : "border-white/[0.045] bg-white/[0.018] text-zinc-500"
                    }
                  `}
                >
                  {msg.text}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Composer */}

      <div className="shrink-0 px-4 pb-3 pt-2">
        <div className="mx-auto w-full max-w-[680px]">
          <div
            className="
              flex
              items-center
              gap-1.5
              rounded-[8px]
              border
              border-white/[0.065]
              bg-[#060607]/95
              p-1
              shadow-[0_15px_50px_rgba(0,0,0,.35)]
              transition
              focus-within:border-violet-400/[0.14]
            "
          >
            <input
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  sendMessage();
                }
              }}
              placeholder="Message DOOF..."
              className="
                min-w-0
                flex-1
                bg-transparent
                px-2.5
                py-2
                text-[10px]
                text-zinc-300
                outline-none
                placeholder:text-zinc-800
              "
            />

            <button
              onClick={sendMessage}
              className="
                rounded-[6px]
                border
                border-violet-400/[0.12]
                bg-violet-500/[0.08]
                px-3
                py-1.5
                text-[8px]
                font-semibold
                uppercase
                tracking-[0.08em]
                text-violet-300
                transition
                hover:bg-violet-500/[0.14]
                hover:text-violet-200
                active:scale-[0.97]
              "
            >
              Send
            </button>
          </div>

          <div className="mt-1.5 text-center text-[6px] uppercase tracking-[0.14em] text-zinc-900">
            DOOF · local inference · CUDA
          </div>
        </div>
      </div>
    </div>
  );
}

/* ============================================================= */
/* EMPTY CHAT                                                     */
/* ============================================================= */

function EmptyChat() {
  return (
    <div className="flex h-full items-center justify-center">
      <div className="-mt-8 text-center">
        <div
          className="
            mx-auto
            flex
            h-[38px]
            w-[38px]
            items-center
            justify-center
            rounded-[9px]
            border
            border-violet-400/[0.1]
            bg-violet-500/[0.035]
            text-[13px]
            font-semibold
            text-violet-400/80
            shadow-[0_0_35px_rgba(139,92,246,.04)]
          "
        >
          D
        </div>

        <h1 className="mt-3 text-[17px] font-semibold tracking-[-0.04em] text-zinc-300">
          DOOF
        </h1>

        <p className="mt-1 text-[8px] text-zinc-700">
          Your own locally trained model.
        </p>

        <div
          className="
            mx-auto
            mt-3
            inline-flex
            items-center
            gap-1.5
            rounded-[5px]
            border
            border-white/[0.045]
            bg-white/[0.012]
            px-2
            py-1
          "
        >
          <span className="h-1 w-1 rounded-full bg-emerald-400/80" />

          <span className="text-[6px] uppercase tracking-[0.12em] text-zinc-700">
            Brain loaded
          </span>
        </div>
      </div>
    </div>
  );
}

/* ============================================================= */
/* PLACEHOLDER                                                    */
/* ============================================================= */

function PlaceholderPage({ page }: { page: Page }) {
  const names: Record<Page, string> = {
    chat: "Chat",
    knowledge: "Knowledge",
    training: "Training",
    models: "Models",
    hardware: "Hardware",
    settings: "Settings",
  };

  return (
    <div className="flex flex-1 items-center justify-center">
      <div className="text-center">
        <div className="text-[7px] uppercase tracking-[0.18em] text-zinc-800">
          {names[page]}
        </div>

        <div className="mt-2 text-[15px] font-semibold tracking-[-0.03em] text-zinc-500">
          DOOF subsystem
        </div>

        <div className="mt-1 text-[8px] text-zinc-800">
          This module is being built.
        </div>
      </div>
    </div>
  );
}

export default App;