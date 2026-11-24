import "server-only";
import { createCipheriv, createDecipheriv, randomBytes, createHash } from "node:crypto";
import { NextRequest, NextResponse } from "next/server";

const COOKIE="am_secure_session";
const MAX_AGE=60*60*24*30;
type Tokens={access_token:string;refresh_token:string};
export type Account={id:string;email:string};

function settings(){
  const url=process.env.SUPABASE_URL?.trim().replace(/\/+$/,"");
  const key=process.env.SUPABASE_PUBLISHABLE_KEY?.trim();
  const secret=process.env.AUTH_COOKIE_SECRET?.trim();
  if(!url||!url.startsWith("https://")||!key||!secret||secret.length<32){
    throw new Error("Server authentication is not configured");
  }
  return {url,key,secret};
}
function seal(value:Tokens):string{
  const secret=settings().secret;
  const key=createHash("sha256").update(secret).digest();
  const iv=randomBytes(12);
  const cipher=createCipheriv("aes-256-gcm",key,iv);
  const body=Buffer.concat([cipher.update(JSON.stringify(value),"utf8"),cipher.final()]);
  return Buffer.concat([iv,cipher.getAuthTag(),body]).toString("base64url");
}
function open(raw:string):Tokens|null{
  try{
    if(raw.length>4096)return null;
    const bytes=Buffer.from(raw,"base64url");
    if(bytes.length<29)return null;
    const key=createHash("sha256").update(settings().secret).digest();
    const decipher=createDecipheriv("aes-256-gcm",key,bytes.subarray(0,12));
    decipher.setAuthTag(bytes.subarray(12,28));
    const parsed:unknown=JSON.parse(Buffer.concat([
      decipher.update(bytes.subarray(28)),decipher.final()
    ]).toString("utf8"));
    if(!parsed||typeof parsed!=="object")return null;
    const obj=parsed as Partial<Tokens>;
    if(typeof obj.access_token!=="string"||typeof obj.refresh_token!=="string")return null;
    if(obj.access_token.length<20||obj.refresh_token.length<20)return null;
    return {access_token:obj.access_token,refresh_token:obj.refresh_token};
  }catch{return null}
}
function cookieOptions(){
  return {httpOnly:true,secure:process.env.NODE_ENV==="production",
    sameSite:"lax" as const,path:"/",maxAge:MAX_AGE,priority:"high" as const};
}
export function setSession(response:NextResponse,tokens:Tokens){
  response.cookies.set(COOKIE,seal(tokens),cookieOptions());
}
export function clearSession(response:NextResponse){
  response.cookies.set(COOKIE,"",{...cookieOptions(),maxAge:0});
}
export function mutationAllowed(req:NextRequest):boolean{
  // Deny cross-origin and missing-origin mutations (login CSRF).
  const origin=req.headers.get("origin");
  if(!origin||origin!==(new URL(req.url)).origin)return false;
  const fetchSite=req.headers.get("sec-fetch-site");
  return !fetchSite||fetchSite==="same-origin";
}
export async function authFetch(path:string,body:Record<string,unknown>,
  method:"POST"|"GET"="POST"){
  const {url,key}=settings();
  const response=await fetch(url+"/auth/v1/"+path,{
    method,
    headers:{"apikey":key,"Content-Type":"application/json"},
    body:method==="POST"?JSON.stringify(body):undefined,
    cache:"no-store",signal:AbortSignal.timeout(12000)
  });
  const data:unknown=await response.json().catch(()=>({}));
  return {ok:response.ok,status:response.status,
    data:typeof data==="object"&&data?data as Record<string,unknown>:{}};
}
export async function verifyTokens(tokens:Tokens):Promise<Account|null>{
  const {url,key}=settings();
  const response=await fetch(url+"/auth/v1/user",{
    headers:{"apikey":key,"Authorization":"Bearer "+tokens.access_token},
    cache:"no-store",signal:AbortSignal.timeout(12000)
  });
  if(!response.ok)return null;
  const user=await response.json() as Record<string,unknown>;
  if(typeof user.id!=="string"||typeof user.email!=="string"||
     !user.email_confirmed_at)return null;
  return {id:user.id,email:user.email};
}
export function extractTokens(body:Record<string,unknown>):Tokens|null{
  const access=body.access_token,refresh=body.refresh_token;
  if(typeof access!=="string"||typeof refresh!=="string"||
     access.length<20||refresh.length<20)return null;
  return {access_token:access,refresh_token:refresh};
}
export async function readSession(req:NextRequest){
  const stored=req.cookies.get(COOKIE)?.value;
  const tokens=stored?open(stored):null;
  if(!tokens)return {account:null as Account|null,tokens:null as Tokens|null,rotate:false};
  let account=await verifyTokens(tokens);
  if(account)return {account,tokens,rotate:false};
  // Supabase access tokens may expire, but the rotating refresh token lives
  // only inside our encrypted HttpOnly cookie.
  const refreshed=await authFetch("token?grant_type=refresh_token",{
    refresh_token:tokens.refresh_token
  });
  const next=refreshed.ok?extractTokens(refreshed.data):null;
  account=next?await verifyTokens(next):null;
  return {account,tokens:account?next:null,rotate:!!account};
}
export function notStored(reply:NextResponse){
  reply.headers.set("Cache-Control","no-store, private");
  reply.headers.set("Pragma","no-cache");
  return reply;
}
