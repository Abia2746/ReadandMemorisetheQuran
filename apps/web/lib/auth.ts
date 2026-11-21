"use client";
import { useCallback, useEffect, useState } from "react";
import { UserManager, WebStorageStateStore, type User } from "oidc-client-ts";

let manager:UserManager|null=null;
const UPDATE_EVENT="almuallim:auth-update";
function getManager():UserManager|null{
  if(typeof window==="undefined")return null;
  const authority=process.env.NEXT_PUBLIC_OIDC_AUTHORITY;
  const clientId=process.env.NEXT_PUBLIC_OIDC_CLIENT_ID;
  if(!authority||!clientId)return null;
  if(!manager){
    manager=new UserManager({
      authority,client_id:clientId,response_type:"code",
      scope:"openid profile email",
      redirect_uri:window.location.origin+"/auth/callback/",
      post_logout_redirect_uri:window.location.origin+"/",
      automaticSilentRenew:false,
      userStore:new WebStorageStateStore({store:window.sessionStorage}),
      monitorSession:false,
    });
  }
  return manager;
}
export async function accessToken():Promise<string>{
  const client=getManager();
  if(!client)throw Error("Sign-in service not configured");
  const user=await client.getUser();
  if(!user||user.expired||!user.access_token)throw Error("Sign in to save your study and access the free AI lesson allowance");
  return user.access_token;
}
export async function beginLogin(){
  const client=getManager();
  if(!client)throw Error("Sign-in service is not configured");
  await client.signinRedirect({state:{returnTo:window.location.pathname+window.location.search}});
}
export async function finishLogin():Promise<void>{
  const client=getManager();
  if(!client)throw Error("Sign-in service not configured");
  const user=await client.signinRedirectCallback();
  window.dispatchEvent(new Event(UPDATE_EVENT));
  const state=user.state as {returnTo?:string}|undefined;
  const target=state?.returnTo&&state.returnTo.startsWith("/")&&!state.returnTo.startsWith("//")
    ?state.returnTo:"/";
  window.location.replace(target);
}
export async function logOut(){
  await getManager()?.signoutRedirect();
}
export function useStudyAuth(){
  const [user,setUser]=useState<User|null>(null);
  const [loading,setLoading]=useState(true);
  const configured=Boolean(process.env.NEXT_PUBLIC_OIDC_AUTHORITY&&process.env.NEXT_PUBLIC_OIDC_CLIENT_ID);
  useEffect(()=>{
    let mounted=true;
    const read=()=>{void getManager()?.getUser().then(value=>{if(mounted)setUser(value)})
      .catch(()=>{if(mounted)setUser(null)})
      .finally(()=>{if(mounted)setLoading(false)});
    };
    if(!configured){setLoading(false);return}
    read();
    window.addEventListener(UPDATE_EVENT,read);
    return()=>{mounted=false;window.removeEventListener(UPDATE_EVENT,read)};
  },[configured]);
  return {user,loading,configured,isSignedIn:Boolean(user&&!user.expired),
    signIn:beginLogin,signOut:logOut,getToken:accessToken};
}
