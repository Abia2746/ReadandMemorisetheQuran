import { NextRequest, NextResponse } from "next/server";
import { authFetch, clearSession, extractTokens, mutationAllowed,
  notStored, readSession, setSession, verifyTokens } from "@/lib/serverSession";

export const runtime="nodejs";
export const dynamic="force-dynamic";

function reply(data:Record<string,unknown>,status=200){
  return notStored(NextResponse.json(data,{status}));
}
export async function GET(req:NextRequest){
  try{
    const {account,tokens,rotate}=await readSession(req);
    const response=reply(account?{signedIn:true,user:account}:{signedIn:false});
    if(rotate&&tokens)setSession(response,tokens);
    if(!account&&req.cookies.has("am_secure_session"))clearSession(response);
    return response;
  }catch{return reply({signedIn:false,configured:false},503)}
}
export async function POST(req:NextRequest){
  if(!mutationAllowed(req))return reply({error:"Invalid request origin"},403);
  if((Number(req.headers.get("content-length"))||0)>2048)
    return reply({error:"Request too large"},413);
  let body:Record<string,unknown>;
  try{
    const raw=await req.text();
    if(raw.length>2048)return reply({error:"Request too large"},413);
    const parsed:unknown=JSON.parse(raw);
    if(!parsed||typeof parsed!=="object"||Array.isArray(parsed))
      return reply({error:"Invalid request"},400);
    body=parsed as Record<string,unknown>;
  }catch{return reply({error:"Invalid request"},400)}
  const action=body.action;
  if(action==="logout"){
    let tokens:ReturnType<typeof extractTokens>=null;
    try{tokens=(await readSession(req)).tokens}catch{}
    // Best-effort Supabase session revocation, never block local signout.
    if(tokens){
      try{
        const url=process.env.SUPABASE_URL?.replace(/\/+$/,"");
        const key=process.env.SUPABASE_PUBLISHABLE_KEY;
        if(url&&key)await fetch(url+"/auth/v1/logout",{
          method:"POST",headers:{"apikey":key,"Authorization":"Bearer "+tokens.access_token},
          cache:"no-store",signal:AbortSignal.timeout(7000)
        });
      }catch{}
    }
    const response=reply({ok:true});
    clearSession(response);
    return response;
  }
  if(action!=="send"&&action!=="verify")return reply({error:"Unsupported action"},400);
  const email=typeof body.email==="string"?body.email.trim().toLowerCase():"";
  if(email.length>254||!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email))
    return reply({error:"Enter a valid email address"},400);
  try{
    if(action==="send"){
      // Supabase enforces per-email and global delivery/abuse limits.
      const createAccount=body.createAccount===true;
      const response=await authFetch("otp",{email,create_user:createAccount});
      if(!response.ok){
        return reply({error:response.status===429
          ?"Email delivery is temporarily limited. Try again later."
          :"Could not send the email. Please try later."},response.status===429?429:503);
      }
      return reply({ok:true,message:"Check your email for a one-time code."});
    }
    const code=typeof body.code==="string"?body.code.trim():"";
    if(!/^[0-9]{6,8}$/.test(code))return reply({error:"Enter your email verification code"},400);
    const verified=await authFetch("verify",{email,token:code,type:"email"});
    if(!verified.ok)return reply({error:"Incorrect, used or expired code"},401);
    const tokens=extractTokens(verified.data);
    const account=tokens?await verifyTokens(tokens):null;
    if(!tokens||!account||account.email.toLowerCase()!==email)
      return reply({error:"Email confirmation could not be verified"},401);
    const response=reply({ok:true,user:account});
    setSession(response,tokens);
    return response;
  }catch{return reply({error:"Account service unavailable"},503)}
}
