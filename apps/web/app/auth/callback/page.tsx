"use client";
import { useEffect, useState } from "react";
import { finishLogin } from "@/lib/auth";
export default function AuthCallback(){
  const [error,setError]=useState("");
  useEffect(()=>{void finishLogin().catch(e=>setError(e instanceof Error?e.message:"Sign-in callback failed"))},[]);
  return <main className="am-page py-20 text-center">
    <h1 className="font-editorial text-3xl text-[#D4AF37]">Al-Mu&apos;allim</h1>
    <p className="mt-4 text-[#E6D5B8]">{error||"Completing your secure sign-in…"}</p>
    {error&&<a href="/" className="am-nav-text-link mt-4">Back to the free Qur&apos;an reader</a>}
  </main>;
}
