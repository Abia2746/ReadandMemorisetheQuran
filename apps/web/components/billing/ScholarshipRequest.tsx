"use client";

import { useState } from "react";

type ScholarshipRequestProps = {
  submitRequest: (months: 3 | 6, note: string | null) => Promise<void>;
  onClose: () => void;
};

export function ScholarshipRequest({ submitRequest, onClose }: ScholarshipRequestProps) {
  const [months, setMonths] = useState<3 | 6>(3);
  const [note, setNote] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState("");

  const send = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (submitting) return;
    setSubmitting(true);
    setError("");
    try {
      await submitRequest(months, note.trim() || null);
      setSubmitted(true);
    } catch {
      setError("We couldn't submit this request. Please try again.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section className="rounded-[24px] border border-[#4A3828] bg-[#1A120D] p-6 text-[#F5EBE0]">
      <h2 className="font-editorial text-2xl">Sponsored Qur'an study</h2>
      {submitted ? (
        <div role="status" className="mt-4">
          <p>Your request has been received. We will review it without asking for financial documents.</p>
          <p className="mt-2 text-sm text-[#E6D5B8]">
            Your Qur'an reader, Qari audio and free study tools remain available.
          </p>
          <button type="button" className="mt-5 underline" onClick={onClose}>Back to learning</button>
        </div>
      ) : (
        <form className="mt-4 space-y-5" onSubmit={send}>
          <p className="text-sm leading-relaxed text-[#E6D5B8]">
            If the cost of Pro is difficult right now, you can request a 3- or 6-month
            study scholarship. No proof of hardship is required.
          </p>
          <fieldset>
            <legend className="mb-2 font-semibold text-[#E6D5B8]">Requested access</legend>
            <div className="flex flex-wrap gap-3">
              {[3, 6].map((value) => (
                <label key={value} className="flex items-center gap-2 rounded-xl border border-[#4A3828] bg-[#2A1F18] px-4 py-3">
                  <input
                    type="radio"
                    name="months"
                    value={value}
                    checked={months === value}
                    onChange={() => setMonths(value as 3 | 6)}
                    className="accent-[#D4AF37]"
                  />
                  {value} months
                </label>
              ))}
            </div>
          </fieldset>
          <div>
            <label htmlFor="scholarship-note" className="mb-2 block font-semibold text-[#E6D5B8]">
              Anything you'd like us to know? <span className="font-normal">(Optional)</span>
            </label>
            <textarea
              id="scholarship-note"
              value={note}
              onChange={(event) => setNote(event.target.value.slice(0, 500))}
              maxLength={500}
              rows={3}
              className="w-full resize-y rounded-xl border border-[#4A3828] bg-[#2A1F18] p-3 text-[#F5EBE0] focus-visible:outline-[#D4AF37]"
              placeholder="You can leave this blank."
            />
          </div>
          <button
            type="submit"
            disabled={submitting}
            className="min-h-11 w-full rounded-full bg-[#C8A96E] px-4 py-3 font-semibold text-[#1A120D] disabled:opacity-50"
          >
            {submitting ? "Submitting…" : "Request sponsored access"}
          </button>
          {error && <p role="alert" className="text-sm text-[#FFADAB]">{error}</p>}
          <button type="button" className="block w-full text-center text-sm underline" onClick={onClose}>
            Continue learning for free
          </button>
        </form>
      )}
    </section>
  );
}

export function SponsorStudentGift({
  onGift,
}: { onGift: () => Promise<void> }) {
  const [working, setWorking] = useState(false);
  return (
    <section className="rounded-2xl border border-[#4A3828] bg-[#241913] p-5 text-[#F5EBE0]">
      <h2 className="font-editorial text-xl">Gift a year of Qur'an study</h2>
      <p className="mt-2 text-sm text-[#E6D5B8]">
        A £39.99 contribution can fund up to 12 months of approved
        sponsored study, distributed in 3- or 6-month grants. Funding
        is reviewed and allocated by the Al-Mu'allim team.
      </p>
      <button type="button" disabled={working}
        className="mt-4 min-h-11 rounded-full bg-[#C8A96E] px-5 py-3 font-semibold text-[#1A120D] disabled:opacity-50"
        onClick={async () => {
          if (working) return;
          setWorking(true);
          try { await onGift(); } finally { setWorking(false); }
        }}>
        {working ? "Opening secure checkout…" : "Sponsor a student · £39.99"}
      </button>
      <p className="mt-3 text-xs text-[#C0AB90]">
        Contributions fund app access. Do not describe them as tax-deductible charitable
        donations unless the organisation is legally entitled to do so.
      </p>
    </section>
  );
}
