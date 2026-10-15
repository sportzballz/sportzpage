const crypto = require("crypto");
const { SecretsManagerClient, GetSecretValueCommand } = require("@aws-sdk/client-secrets-manager");

const secrets = new SecretsManagerClient({});
const PRODUCT_ID = process.env.APPLE_PRODUCT_ID;
const BUNDLE_ID = process.env.APPLE_BUNDLE_ID;
const APPLE_APP_ID = Number(process.env.APPLE_APP_ID);
const KEY_PAIR_ID = process.env.CLOUDFRONT_KEY_PAIR_ID;
const COOKIE_DOMAIN = process.env.COOKIE_DOMAIN;
const MAX_SESSION_SECONDS = Number(process.env.MAX_SESSION_SECONDS || "86400");
const ALLOWED_ROOT_FINGERPRINTS = new Set(
  (process.env.APPLE_ROOT_SHA256 || "")
    .split(",")
    .map((value) => value.replaceAll(":", "").toUpperCase())
    .filter(Boolean),
);
const GOOGLE_CREDENTIALS_SECRET = process.env.GOOGLE_CREDENTIALS_SECRET;
const GOOGLE_PACKAGE_NAME = process.env.GOOGLE_PACKAGE_NAME;
const COOKIE_PRIVATE_KEY_SECRET = process.env.COOKIE_PRIVATE_KEY_SECRET;
let googleCredentials;
let googleAccessToken;
let cookiePrivateKey;

function json(statusCode, payload) {
  return {
    statusCode,
    headers: {
      "content-type": "application/json",
      "cache-control": "no-store",
    },
    body: JSON.stringify(payload),
  };
}

function decodeBase64Url(value) {
  return Buffer.from(value, "base64url");
}

function certificateFromBase64(value) {
  const body = value.match(/.{1,64}/g).join("\n");
  return new crypto.X509Certificate(`-----BEGIN CERTIFICATE-----\n${body}\n-----END CERTIFICATE-----`);
}

function verifyCertificateChain(certificates) {
  if (certificates.length < 3) throw new Error("Incomplete Apple certificate chain");

  const now = Date.now();
  for (const certificate of certificates) {
    if (now < Date.parse(certificate.validFrom) || now > Date.parse(certificate.validTo)) {
      throw new Error("Expired Apple signing certificate");
    }
  }

  for (let index = 0; index < certificates.length - 1; index += 1) {
    if (!certificates[index].verify(certificates[index + 1].publicKey)) {
      throw new Error("Invalid Apple certificate chain");
    }
  }

  const root = certificates.at(-1);
  const fingerprint = root.fingerprint256.replaceAll(":", "").toUpperCase();
  if (!ALLOWED_ROOT_FINGERPRINTS.has(fingerprint) || !root.verify(root.publicKey)) {
    throw new Error("Untrusted Apple root certificate");
  }
}

function verifyAppleTransaction(jws) {
  const parts = String(jws || "").split(".");
  if (parts.length !== 3) throw new Error("Invalid transaction token");

  const header = JSON.parse(decodeBase64Url(parts[0]).toString("utf8"));
  if (header.alg !== "ES256" || !Array.isArray(header.x5c)) {
    throw new Error("Unsupported transaction signature");
  }

  const certificates = header.x5c.map(certificateFromBase64);
  verifyCertificateChain(certificates);
  const verified = crypto.verify(
    "sha256",
    Buffer.from(`${parts[0]}.${parts[1]}`),
    { key: certificates[0].publicKey, dsaEncoding: "ieee-p1363" },
    decodeBase64Url(parts[2]),
  );
  if (!verified) throw new Error("Invalid transaction signature");

  const transaction = JSON.parse(decodeBase64Url(parts[1]).toString("utf8"));
  const now = Date.now();
  if (transaction.bundleId !== BUNDLE_ID || transaction.productId !== PRODUCT_ID) {
    throw new Error("Transaction is for a different app or product");
  }
  if (transaction.environment === "Production" && transaction.appAppleId !== APPLE_APP_ID) {
    throw new Error("Transaction is for a different App Store app");
  }
  if (!Number.isFinite(transaction.expiresDate) || transaction.expiresDate <= now) {
    throw new Error("Subscription has expired");
  }
  if (transaction.revocationDate) throw new Error("Subscription was revoked");

  return transaction;
}

function base64UrlJson(value) {
  return Buffer.from(JSON.stringify(value)).toString("base64url");
}

async function getGoogleCredentials() {
  if (googleCredentials) return googleCredentials;
  const result = await secrets.send(new GetSecretValueCommand({ SecretId: GOOGLE_CREDENTIALS_SECRET }));
  googleCredentials = JSON.parse(result.SecretString);
  if (!googleCredentials.client_email || !googleCredentials.private_key) {
    throw new Error("Google Play service account is not configured");
  }
  return googleCredentials;
}

async function getGoogleAccessToken() {
  const now = Math.floor(Date.now() / 1000);
  if (googleAccessToken?.expiresAt > now + 60) return googleAccessToken.value;
  const credentials = await getGoogleCredentials();
  const header = base64UrlJson({ alg: "RS256", typ: "JWT" });
  const claims = base64UrlJson({
    iss: credentials.client_email,
    scope: "https://www.googleapis.com/auth/androidpublisher",
    aud: "https://oauth2.googleapis.com/token",
    iat: now,
    exp: now + 3600,
  });
  const signature = crypto.sign("RSA-SHA256", Buffer.from(`${header}.${claims}`), credentials.private_key);
  const assertion = `${header}.${claims}.${signature.toString("base64url")}`;
  const response = await fetch("https://oauth2.googleapis.com/token", {
    method: "POST",
    headers: { "content-type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      grant_type: "urn:ietf:params:oauth:grant-type:jwt-bearer",
      assertion,
    }),
  });
  if (!response.ok) throw new Error("Google authorization failed");
  const token = await response.json();
  googleAccessToken = { value: token.access_token, expiresAt: now + Number(token.expires_in || 3600) };
  return googleAccessToken.value;
}

async function verifyGooglePurchase(purchaseToken) {
  if (!purchaseToken || String(purchaseToken).length > 4096) throw new Error("Invalid purchase token");
  const accessToken = await getGoogleAccessToken();
  const url = new URL(
    `https://androidpublisher.googleapis.com/androidpublisher/v3/applications/${encodeURIComponent(GOOGLE_PACKAGE_NAME)}/purchases/subscriptionsv2/tokens/${encodeURIComponent(purchaseToken)}`,
  );
  const response = await fetch(url, { headers: { authorization: `Bearer ${accessToken}` } });
  if (!response.ok) throw new Error("Google Play purchase validation failed");
  const purchase = await response.json();
  const permittedStates = new Set([
    "SUBSCRIPTION_STATE_ACTIVE",
    "SUBSCRIPTION_STATE_IN_GRACE_PERIOD",
    "SUBSCRIPTION_STATE_CANCELED",
  ]);
  if (!permittedStates.has(purchase.subscriptionState)) throw new Error("Google Play subscription is inactive");
  const matchingItems = (purchase.lineItems || []).filter((item) => item.productId === PRODUCT_ID);
  const expiresAt = Math.max(...matchingItems.map((item) => Date.parse(item.expiryTime)));
  if (!Number.isFinite(expiresAt) || expiresAt <= Date.now()) throw new Error("Google Play subscription has expired");
  return { expiresDate: expiresAt };
}

function cloudFrontBase64(buffer) {
  return buffer
    .toString("base64")
    .replaceAll("+", "-")
    .replaceAll("=", "_")
    .replaceAll("/", "~");
}

async function issueCookies(transaction) {
  const nowSeconds = Math.floor(Date.now() / 1000);
  const transactionExpiry = Math.floor(transaction.expiresDate / 1000);
  const expiresAt = Math.min(transactionExpiry, nowSeconds + MAX_SESSION_SECONDS);
  const policy = JSON.stringify({
    Statement: [{
      Resource: `https://${COOKIE_DOMAIN}/subscriber/*`,
      Condition: { DateLessThan: { "AWS:EpochTime": expiresAt } },
    }],
  });
  if (!cookiePrivateKey) {
    const result = await secrets.send(
      new GetSecretValueCommand({ SecretId: COOKIE_PRIVATE_KEY_SECRET }),
    );
    cookiePrivateKey = result.SecretString;
  }
  const signature = crypto.sign("RSA-SHA1", Buffer.from(policy), cookiePrivateKey);
  const attributes = `Domain=${COOKIE_DOMAIN}; Path=/subscriber; Max-Age=${expiresAt - nowSeconds}; Secure; HttpOnly; SameSite=Lax`;
  return [
    `CloudFront-Policy=${cloudFrontBase64(Buffer.from(policy))}; ${attributes}`,
    `CloudFront-Signature=${cloudFrontBase64(signature)}; ${attributes}`,
    `CloudFront-Key-Pair-Id=${KEY_PAIR_ID}; ${attributes}`,
  ];
}

exports.handler = async (event) => {
  if (event.requestContext?.http?.method !== "POST") {
    return json(405, { ok: false, error: "Method not allowed." });
  }

  let body;
  try {
    body = JSON.parse(event.body || "{}");
  } catch {
    return json(400, { ok: false, error: "Invalid request." });
  }

  try {
    const isGoogle = event.rawPath?.endsWith("/google");
    const transaction = isGoogle
      ? await verifyGooglePurchase(body.purchaseToken)
      : verifyAppleTransaction(body.signedTransaction);
    const cookies = await issueCookies(transaction);
    return {
      statusCode: 204,
      headers: { "cache-control": "no-store" },
      cookies,
    };
  } catch (error) {
    console.warn("Access denied", error.message);
    return json(403, { ok: false, error: "An active App Store subscription is required." });
  }
};
