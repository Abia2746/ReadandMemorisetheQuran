// Al-Mu'allim Stripe Sandbox webhook. Test-only and fail-closed.
// Incoming requests require a valid Stripe-Signature over the raw body.
// Private keys must be stored as Supabase Edge Function secrets.
const json = (value: unknown, status = 200) =>
  new Response(JSON.stringify(value), {
    status, headers: {"content-type": "application/json; charset=utf-8"}
  });

const enc = new TextEncoder();
function constantTimeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let mismatch = 0;
  for (let i = 0; i < a.length; i++) mismatch |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return mismatch === 0;
}
async function verifiedStripeSignature(
  raw: string, signature: string | null, signingSecret: string
): Promise<boolean> {
  if (!signature || !signingSecret.startsWith("whsec_")) return false;
  const entries = signature.split(",").map((part) => part.trim().split("="));
  const timestamp = entries.find(([key]) => key === "t")?.[1];
  const v1 = entries.filter(([key]) => key === "v1").map(([,sig]) => sig);
  if (!timestamp || !/^\d{10,12}$/.test(timestamp) || !v1.length) return false;
  if (Math.abs(Date.now() / 1000 - Number(timestamp)) > 300) return false;
  const cryptoKey = await crypto.subtle.importKey(
    "raw", enc.encode(signingSecret), {name:"HMAC", hash:"SHA-256"}, false, ["sign"]
  );
  const bytes = new Uint8Array(await crypto.subtle.sign(
    "HMAC", cryptoKey, enc.encode(timestamp + "." + raw)
  ));
  const digest = Array.from(bytes, b => b.toString(16).padStart(2,"0")).join("");
  return v1.some((signatureValue) => /^[a-f0-9]{64}$/i.test(signatureValue)
    && constantTimeEqual(digest, signatureValue.toLowerCase()));
}

Deno.serve(async (request: Request) => {
  if (request.method !== "POST") return json({error:"Method not allowed"},405);
  const signingSecret = Deno.env.get("STRIPE_WEBHOOK_SIGNING_SECRET") || "";
  const apiKey = Deno.env.get("STRIPE_API_KEY") || "";
  const supabaseUrl = Deno.env.get("SUPABASE_URL") || "";
  const serviceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";
  // Deliberately prevent live billing until an authorised adult and the
  // owner complete merchant verification, legal requirements and QA.
  if (!signingSecret || !apiKey.startsWith("sk_test_") ||
      !supabaseUrl || !serviceKey) {
    return json({error:"Sandbox webhook is not configured"},503);
  }
  let raw: string;
  try {
    raw = await request.text();
    if (raw.length > 262144) return json({error:"Event too large"},413);
    if (!await verifiedStripeSignature(raw, request.headers.get("stripe-signature"), signingSecret))
      return json({error:"Invalid signature"},400);
  } catch {
    return json({error:"Could not verify webhook"},400);
  }
  let event: Record<string, any>;
  try {event = JSON.parse(raw);} catch {return json({error:"Invalid JSON"},400);}
  if (event.livemode !== false) return json({error:"Sandbox events only"},400);
  const kind = String(event.type || "");
  const supported = new Set([
    "checkout.session.completed", "customer.subscription.created",
    "customer.subscription.updated", "customer.subscription.deleted"
  ]);
  if (!supported.has(kind)) return json({received:true, ignored:true});
  const obj = event.data?.object || {};
  const subscriptionId: unknown = kind === "checkout.session.completed"
      ? obj.subscription : obj.id;
  if (typeof subscriptionId !== "string" || !/^sub_[A-Za-z0-9]+$/.test(subscriptionId))
    return json({received:true, ignored:true});

  // Retrieve authoritative, latest subscription state from Stripe, not from
  // a potentially delayed/out-of-order webhook payload.
  const subscriptionResponse = await fetch(
    "https://api.stripe.com/v1/subscriptions/" + encodeURIComponent(subscriptionId),
    {headers: {"authorization": "Bearer " + apiKey}}
  );
  if (!subscriptionResponse.ok) return json({error:"Stripe lookup failed"},502);
  const subscription = await subscriptionResponse.json();
  if (subscription.livemode !== false) return json({error:"Live subscription refused"},400);
  const userId = subscription.metadata?.supabase_user_id;
  if (typeof userId !== "string" ||
      !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(userId))
    return json({received:true, ignored:true});
  const customerId = typeof subscription.customer === "string"
    ? subscription.customer : subscription.customer?.id;
  const firstItem = subscription.items?.data?.[0];
  const priceId = firstItem?.price?.id;
  const supportedPrices = new Set([
    "price_1UecayRyfWQC5psUg8pXdLRq",
    "price_1UeciwRyfWQC5psU1n56spbe",
    "price_1UecgVRyfWQC5psUPS3B8LWa"
  ]);
  if (typeof customerId !== "string" || !supportedPrices.has(priceId))
    return json({received:true, ignored:true});
  const periodEnd = firstItem?.current_period_end ?? subscription.current_period_end;
  const row = {
    user_id: userId,
    stripe_subscription_id: subscriptionId,
    stripe_customer_id: customerId,
    stripe_price_id: priceId,
    status: String(subscription.status),
    current_period_end: typeof periodEnd === "number"
      ? new Date(periodEnd * 1000).toISOString() : null,
    updated_at: new Date().toISOString(),
  };
  const result = await fetch(
    supabaseUrl + "/rest/v1/billing_subscriptions?on_conflict=stripe_subscription_id",
    {
      method: "POST",
      headers: {
        "apikey": serviceKey, "authorization": "Bearer " + serviceKey,
        "content-type":"application/json",
        "prefer":"resolution=merge-duplicates,return=minimal"
      },
      body: JSON.stringify(row)
    }
  );
  if (!result.ok) return json({error:"Subscription sync failed"},502);
  return json({received:true});
});
