"use client";
import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";

type Account={id:string;email:string};
type State="loading"|"signed-out"|"email-sent"|"signed-in";
type AccountResponse={signedIn?:boolean;configured?:boolean;user?:Account;ok?:boolean;error?:string};

async function requestAccount(body?:Record<string,unknown>):Promise<AccountResponse>{
  const response=await fetch("/api/account",{
    method:body?"POST":"GET",
    headers:body?{"Content-Type":"application/json"}:undefined,
    body:body?JSON.stringify(body):undefined,
    cache:"no-store",credentials:"same-origin"
  });
  const data=await response.json() as AccountResponse;
  if(!response.ok)throw Error(data.error||"Account service is unavailable");
  return data;
}
export default function AccountPage(){
  const [status,setStatus]=useState<State>("loading");
  const [user,setUser]=useState<Account|null>(null);
  const [email,setEmail]=useState("");
  const [otp,setOtp]=useState("");
  const [creating,setCreating]=useState(true);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState("");
  const [notice,setNotice]=useState("");
  useEffect(()=>{
    let mounted=true;
    const query=new URLSearchParams(window.location.search);
    if(query.has("error"))setNotice("This email link could not be verified. Request a new code.");
    else if(query.get("confirmed")==="1")setNotice("Your email is confirmed.");
    void requestAccount().then(value=>{
      if(!mounted)return;
      if(value.signedIn&&value.user){setUser(value.user);setStatus("signed-in");}
      else{setStatus("signed-out");if(value.configured===false)
        setError("Secure account service has not been configured on this deployment.");}
    }).catch(()=>{if(mounted){setStatus("signed-out");setError("Account service is unavailable.");}});
    return()=>{mounted=false};
  },[]);
  const send=async(event:FormEvent<HTMLFormElement>)=>{
    event.preventDefault();setBusy(true);setError("");setNotice("");
    try{
      await requestAccount({action:"send",email,createAccount:creating});
      setStatus("email-sent");
      setNotice("Check your inbox. Enter the one-time code from the latest Al-Mu'allim email.");
    }catch(e){setError(e instanceof Error?e.message:"Could not send the code")}
    finally{setBusy(false)}
  };
  const verify=async(event:FormEvent<HTMLFormElement>)=>{
    event.preventDefault();setBusy(true);setError("");
    try{
      const result=await requestAccount({action:"verify",email,code:otp});
      if(result.user){setUser(result.user);setStatus("signed-in");setOtp("");setNotice("Email verified. Your account is signed in.");}
    }catch(e){setError(e instanceof Error?e.message:"Could not verify the code")}
    finally{setBusy(false)}
  };
  const logout=async()=>{
    setBusy(true);setError("");
    try{
      await requestAccount({action:"logout"});
      setUser(null);setStatus("signed-out");setOtp("");setNotice("You've signed out.");
    }catch(e){setError(e instanceof Error?e.message:"Could not sign out")}
    finally{setBusy(false)}
  };
  return <main className="am-page min-h-[75vh] flex items-center justify-center py-14">
    <section className="w-full max-w-[490px] rounded-[28px] border border-[#806848]/50 bg-[#241913] p-6 sm:p-10 shadow-2xl">
      <div className="mx-auto mb-5 grid size-14 place-items-center rounded-2xl border border-[#c8a96e]/50 text-[#edd39f] text-3xl">✧</div>
      <p className="text-center uppercase tracking-[.22em] text-[#c8a96e] text-xs">Al-Mu&apos;allim · Your account</p>
      <h1 className="text-center font-[family-name:var(--font-editorial)] text-4xl leading-tight mt-3 mb-3 text-[#f5ebde]">
        Your journey, beautifully kept.
      </h1>
      <p className="text-center text-[#c8b9a5] leading-relaxed mb-8">
        Securely return to your Qur&apos;an learning and saved progress.
      </p>
      {notice&&<p role="status" className="rounded-xl bg-[#18382a] text-[#d8e6d7] p-3 mb-4">{notice}</p>}
      {error&&<p role="alert" className="rounded-xl bg-[#593323] text-[#ffe4d5] p-3 mb-4">{error}</p>}
      {status==="loading"&&<p className="text-center">Checking your session…</p>}
      {status==="signed-in"&&<div className="text-center space-y-5">
        <p className="text-[#edd39f] font-semibold">Email confirmed · Signed in</p>
        <p className="break-all">{user?.email}</p>
        <p className="text-sm text-[#c8b9a5]">This account session is stored in a protected browser cookie. Payments and premium access are not yet enabled.</p>
        <button type="button" disabled={busy} onClick={()=>void logout()}
          className="am-pill mx-auto">{busy?"Signing out…":"Sign out"}</button>
      </div>}
      {status==="signed-out"&&<form onSubmit={e=>void send(e)} className="space-y-5">
        <div className="flex gap-2 rounded-full p-1 border border-[#4a3828]">
          <button type="button" aria-pressed={creating} onClick={()=>setCreating(true)}
            className={"flex-1 rounded-full p-2 "+(creating?"bg-[#c8a96e] text-[#241913]":"text-[#f5ebde]")}>Create account</button>
          <button type="button" aria-pressed={!creating} onClick={()=>setCreating(false)}
            className={"flex-1 rounded-full p-2 "+(!creating?"bg-[#c8a96e] text-[#241913]":"text-[#f5ebde]")}>Sign in</button>
        </div>
        <label className="block"><span className="am-field-label">Email address</span>
          <input className="am-field" type="email" required autoComplete="email" maxLength={254}
            value={email} onChange={e=>setEmail(e.target.value)} placeholder="you@example.com"/>
        </label>
        <button disabled={busy} type="submit"
          className="w-full min-h-12 rounded-xl font-semibold text-[#241913] bg-[#d4af78] disabled:opacity-60">
          {busy?"Requesting…":"Continue with email"}
        </button>
      </form>}
      {status==="email-sent"&&<form onSubmit={e=>void verify(e)} className="space-y-5">
        <p className="text-center text-sm text-[#d8c8b4] break-all">{email}</p>
        <label className="block"><span className="am-field-label">Email verification code</span>
          <input className="am-field text-center tracking-[.35em] text-xl" type="text"
            autoComplete="one-time-code" inputMode="numeric" pattern="[0-9]{6,8}"
            minLength={6} maxLength={8} required value={otp}
            onChange={e=>setOtp(e.target.value.replace(/[^0-9]/g,""))} placeholder="••••••"/>
        </label>
        <button disabled={busy} type="submit"
          className="w-full min-h-12 rounded-xl font-semibold text-[#241913] bg-[#d4af78] disabled:opacity-60">
          {busy?"Verifying…":"Verify and continue"}
        </button>
        <button type="button" className="am-pill mx-auto" onClick={()=>{setStatus("signed-out");setOtp("");}}>
          Use another email or resend
        </button>
      </form>}
      <p className="mt-7 text-xs leading-relaxed text-[#c8b9a5] text-center">
        No password needed. Qur&apos;an reading remains free without an account.
      </p>
      <div className="mt-5 text-center"><Link className="text-[#edd39f] underline" href="/">Continue to free Qur&apos;an reader</Link></div>
    </section>
  </main>
}
