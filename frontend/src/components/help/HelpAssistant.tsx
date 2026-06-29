import { useMemo, useState } from "react";
import { MessageCircle, X, Send, Paperclip, LifeBuoy } from "lucide-react";
import { createHelpTicket, sendHelpMessage } from "@/lib/api";
import { Language, useI18n } from "@/lib/i18n";

type HelpMessage = {
  role: "user" | "assistant";
  text: string;
  source?: string;
};

const ISSUE_TYPES = [
  "account",
  "amazon_authorization",
  "data_upload",
  "report_issue",
  "billing",
  "privacy_request",
  "security_issue",
  "bug_report",
  "feature_request",
  "other",
];

const PRIORITIES = ["low", "medium", "high", "urgent"];

export default function HelpAssistant() {
  const { t, language, setLanguage } = useI18n();
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<HelpMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [ticketOpen, setTicketOpen] = useState(false);
  const [ticketMessage, setTicketMessage] = useState("");
  const [issueType, setIssueType] = useState("other");
  const [priority, setPriority] = useState("medium");
  const [notice, setNotice] = useState("");

  const quickQuestions = useMemo(() => [
    t("help.quick.1"),
    t("help.quick.2"),
    t("help.quick.3"),
    t("help.quick.4"),
    t("help.quick.5"),
    t("help.quick.6"),
  ], [t, language]);

  const ask = async (message: string) => {
    const trimmed = message.trim();
    if (!trimmed) return;
    setMessages((prev) => [...prev, { role: "user", text: trimmed }]);
    setInput("");
    setLoading(true);
    setNotice("");
    try {
      const result = await sendHelpMessage({
        message: trimmed,
        language,
        page_url: window.location.href,
      });
      setMessages((prev) => [...prev, { role: "assistant", text: result.answer, source: result.source }]);
      if (result.should_create_ticket) {
        setTicketOpen(true);
        setTicketMessage(trimmed);
        setIssueType(result.suggested_issue_type || "other");
        setNotice(t("help.ticketHint"));
      }
    } catch (error) {
      setMessages((prev) => [...prev, { role: "assistant", text: error instanceof Error ? error.message : t("help.askFailed"), source: "fallback" }]);
    } finally {
      setLoading(false);
    }
  };

  const submitTicket = async () => {
    const message = (ticketMessage || input).trim();
    if (!message) return;
    setLoading(true);
    setNotice("");
    try {
      const ticket = await createHelpTicket({
        issue_type: issueType,
        priority,
        language,
        page_url: window.location.href,
        user_message: message,
        screenshots: [],
      });
      setNotice(`${t("help.ticketCreated")}: ${ticket.ticket_id}`);
      setTicketOpen(false);
      setTicketMessage("");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : t("help.ticketFailed"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <HelpAssistantButton label={t("help.button")} onClick={() => setOpen(true)} />
      {open && (
        <HelpAssistantDrawer
          language={language}
          setLanguage={setLanguage}
          messages={messages}
          quickQuestions={quickQuestions}
          input={input}
          setInput={setInput}
          loading={loading}
          notice={notice}
          ticketOpen={ticketOpen}
          setTicketOpen={setTicketOpen}
          ticketMessage={ticketMessage}
          setTicketMessage={setTicketMessage}
          issueType={issueType}
          setIssueType={setIssueType}
          priority={priority}
          setPriority={setPriority}
          onClose={() => setOpen(false)}
          onAsk={ask}
          onSubmitTicket={submitTicket}
          t={t}
        />
      )}
    </>
  );
}

function HelpAssistantButton({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="fixed bottom-6 right-6 z-40 flex items-center gap-2 rounded-full border border-[#0F2A24]/12 bg-white px-5 py-3 text-[14px] font-semibold text-[#0F2A24] shadow-[0_18px_50px_rgba(15,42,36,0.18)] transition-transform active:scale-[0.98]"
    >
      <MessageCircle size={18} />
      {label}
    </button>
  );
}

function HelpAssistantDrawer(props: {
  language: Language;
  setLanguage: (language: Language) => void;
  messages: HelpMessage[];
  quickQuestions: string[];
  input: string;
  setInput: (value: string) => void;
  loading: boolean;
  notice: string;
  ticketOpen: boolean;
  setTicketOpen: (open: boolean) => void;
  ticketMessage: string;
  setTicketMessage: (value: string) => void;
  issueType: string;
  setIssueType: (value: string) => void;
  priority: string;
  setPriority: (value: string) => void;
  onClose: () => void;
  onAsk: (message: string) => void;
  onSubmitTicket: () => void;
  t: (key: string) => string;
}) {
  const {
    language, setLanguage, messages, quickQuestions, input, setInput, loading, notice,
    ticketOpen, setTicketOpen, ticketMessage, setTicketMessage, issueType, setIssueType,
    priority, setPriority, onClose, onAsk, onSubmitTicket, t,
  } = props;
  return (
    <div className="fixed inset-0 z-50 bg-[#1d1d1f]/20">
      <aside className="fixed bottom-0 right-0 top-0 flex w-full max-w-[420px] flex-col border-l border-[#d2d2d7]/60 bg-white shadow-2xl">
        <div className="border-b border-[#d2d2d7]/50 p-5">
          <div className="flex items-start gap-3">
            <div className="mt-0.5 flex h-10 w-10 items-center justify-center rounded-2xl bg-[#0F2A24] text-white">
              <LifeBuoy size={19} />
            </div>
            <div className="min-w-0 flex-1">
              <h2 className="text-[17px] font-semibold text-[#1d1d1f]">{t("help.title")}</h2>
              <p className="mt-1 text-[13px] leading-relaxed text-[#86868b]">{t("help.subtitle")}</p>
            </div>
            <button onClick={onClose} className="rounded-full p-2 text-[#86868b] hover:bg-[#fbfaf7]" aria-label={t("help.close")}>
              <X size={18} />
            </button>
          </div>
          <div className="mt-4 flex items-center justify-between gap-3">
            <select
              value={language}
              onChange={(event) => setLanguage(event.target.value === "en" ? "en" : "zh")}
              className="rounded-full border border-[#d2d2d7] bg-white px-3 py-2 text-[13px]"
              aria-label={t("language.label")}
            >
              <option value="zh">中文</option>
              <option value="en">English</option>
            </select>
            <button onClick={() => setTicketOpen(!ticketOpen)} className="rounded-full bg-[#0F2A24] px-4 py-2 text-[13px] font-medium text-white">
              {t("help.createTicket")}
            </button>
          </div>
        </div>

        <HelpAssistantMessageList messages={messages} emptyText={t("help.quickQuestions")} />
        <HelpAssistantQuickQuestions questions={quickQuestions} onAsk={onAsk} />
        {ticketOpen && (
          <HelpTicketForm
            t={t}
            ticketMessage={ticketMessage}
            setTicketMessage={setTicketMessage}
            issueType={issueType}
            setIssueType={setIssueType}
            priority={priority}
            setPriority={setPriority}
            onSubmit={onSubmitTicket}
            loading={loading}
          />
        )}
        <HelpPolicyLinks language={language} t={t} />
        {notice && <p className="px-5 pb-2 text-[12px] text-[#0F2A24]">{notice}</p>}
        <HelpAssistantInput input={input} setInput={setInput} loading={loading} onAsk={onAsk} t={t} />
      </aside>
    </div>
  );
}

function HelpAssistantMessageList({ messages, emptyText }: { messages: HelpMessage[]; emptyText: string }) {
  return (
    <div className="flex-1 overflow-y-auto px-5 py-4">
      {messages.length === 0 ? (
        <p className="text-[13px] text-[#86868b]">{emptyText}</p>
      ) : (
        <div className="space-y-3">
          {messages.map((message, index) => (
            <div key={`${message.role}-${index}`} className={`rounded-2xl px-4 py-3 text-[14px] leading-relaxed ${message.role === "user" ? "ml-8 bg-[#0F2A24] text-white" : "mr-8 bg-[#fbfaf7] text-[#1d1d1f]"}`}>
              {message.text}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function HelpAssistantQuickQuestions({ questions, onAsk }: { questions: string[]; onAsk: (message: string) => void }) {
  return (
    <div className="border-t border-[#d2d2d7]/40 px-5 py-3">
      <div className="flex flex-wrap gap-2">
        {questions.map((question) => (
          <button key={question} onClick={() => onAsk(question)} className="rounded-full border border-[#d2d2d7] bg-white px-3 py-1.5 text-[12px] text-[#1d1d1f] hover:border-[#0F2A24]/40">
            {question}
          </button>
        ))}
      </div>
    </div>
  );
}

function HelpAssistantInput({ input, setInput, loading, onAsk, t }: { input: string; setInput: (value: string) => void; loading: boolean; onAsk: (message: string) => void; t: (key: string) => string }) {
  return (
    <div className="border-t border-[#d2d2d7]/50 p-5">
      <div className="flex items-end gap-2">
        <button className="mb-1 rounded-full p-2 text-[#86868b] hover:bg-[#fbfaf7]" aria-label={t("help.uploadScreenshot")}>
          <Paperclip size={18} />
        </button>
        <textarea
          value={input}
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              onAsk(input);
            }
          }}
          placeholder={t("help.placeholder")}
          className="min-h-[46px] flex-1 resize-none rounded-2xl border border-[#d2d2d7] px-4 py-3 text-[14px] outline-none focus:border-[#0F2A24] focus:ring-2 focus:ring-[#0F2A24]/10"
        />
        <button disabled={loading || !input.trim()} onClick={() => onAsk(input)} className="mb-1 rounded-full bg-[#0F2A24] p-3 text-white disabled:opacity-40" aria-label={t("help.send")}>
          <Send size={17} />
        </button>
      </div>
    </div>
  );
}

function HelpTicketForm(props: {
  t: (key: string) => string;
  ticketMessage: string;
  setTicketMessage: (value: string) => void;
  issueType: string;
  setIssueType: (value: string) => void;
  priority: string;
  setPriority: (value: string) => void;
  onSubmit: () => void;
  loading: boolean;
}) {
  const { t, ticketMessage, setTicketMessage, issueType, setIssueType, priority, setPriority, onSubmit, loading } = props;
  return (
    <div className="border-t border-[#d2d2d7]/40 bg-[#fbfaf7] p-5">
      <div className="grid grid-cols-2 gap-3">
        <label className="text-[12px] text-[#86868b]">
          {t("help.issueType")}
          <select value={issueType} onChange={(event) => setIssueType(event.target.value)} className="mt-1 w-full rounded-xl border border-[#d2d2d7] bg-white px-3 py-2 text-[13px] text-[#1d1d1f]">
            {ISSUE_TYPES.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
        </label>
        <label className="text-[12px] text-[#86868b]">
          {t("help.priority")}
          <select value={priority} onChange={(event) => setPriority(event.target.value)} className="mt-1 w-full rounded-xl border border-[#d2d2d7] bg-white px-3 py-2 text-[13px] text-[#1d1d1f]">
            {PRIORITIES.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
        </label>
      </div>
      <textarea value={ticketMessage} onChange={(event) => setTicketMessage(event.target.value)} placeholder={t("help.manualMessage")} className="mt-3 min-h-[80px] w-full rounded-xl border border-[#d2d2d7] bg-white px-3 py-2 text-[13px] outline-none focus:border-[#0F2A24]" />
      <button disabled={loading || !ticketMessage.trim()} onClick={onSubmit} className="mt-3 rounded-full bg-[#0F2A24] px-4 py-2 text-[13px] font-medium text-white disabled:opacity-40">
        {loading ? t("help.sending") : t("help.createTicket")}
      </button>
    </div>
  );
}

function HelpPolicyLinks({ language, t }: { language: Language; t: (key: string) => string }) {
  const prefix = language === "en" ? "/en" : "/zh";
  const links = [
    [t("help.privacy"), `${prefix}/privacy-policy`],
    [t("help.terms"), `${prefix}/terms`],
    [t("help.dataUse"), `${prefix}/data-use-policy`],
    [t("help.security"), `${prefix}/security`],
    [t("help.contact"), `${prefix}/contact`],
  ];
  return (
    <div className="border-t border-[#d2d2d7]/40 px-5 py-3">
      <p className="mb-2 text-[12px] font-medium text-[#86868b]">{t("help.policies")}</p>
      <div className="flex flex-wrap gap-x-3 gap-y-1 text-[12px] text-[#0F2A24]">
        {links.map(([label, href]) => <a key={href} href={href}>{label}</a>)}
      </div>
    </div>
  );
}
