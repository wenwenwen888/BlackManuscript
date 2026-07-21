export function onRequest() {
  return new Response(JSON.stringify({ ok: true, service: "satire-daily-functions" }), {
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
      "access-control-allow-origin": "*",
    },
  });
}
