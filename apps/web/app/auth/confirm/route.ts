import { NextRequest, NextResponse } from "next/server";
import { authFetch, extractTokens, notStored, setSession, verifyTokens } from "@/lib/serverSession";

export const runtime="nodejs";
export const dynamic="force-dynamic";

// For Supabase email templates using:
// https://YOUR_APP/auth/confirm?token_hash={{ .TokenHash }}&type=email
export async function GET(request:NextRequest){
  const url=new URL(request.url);
  const hash=url.searchParams.get("token_hash")||"";
  const type=url.searchParams.get("type")||"";
  const target=new URL("/account",url.origin);
  if(!/^[A-Za-z0-9_-]{24,256}$/.test(hash)||
      !["email","signup","magiclink"].includes(type)){
    target.searchParams.set("error","invalid-link");
    return notStored(NextResponse.redirect(target,303));
  }
  try{
    const verified=await authFetch("verify",{token_hash:hash,type});
    const tokens=verified.ok?extractTokens(verified.data):null;
    const account=tokens?await verifyTokens(tokens):null;
    if(!tokens||!account){
      target.searchParams.set("error","expired-link");
      return notStored(NextResponse.redirect(target,303));
    }
    target.searchParams.set("confirmed","1");
    const response=notStored(NextResponse.redirect(target,303));
    setSession(response,tokens);
    return response;
  }catch{
    target.searchParams.set("error","service-unavailable");
    return notStored(NextResponse.redirect(target,303));
  }
}
