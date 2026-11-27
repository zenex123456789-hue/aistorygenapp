export async function api(method, url, body) {
  const opt = { method, headers: {} };
  if (body instanceof FormData) opt.body = body;
  else if (body !== undefined) { opt.headers["Content-Type"] = "application/json"; opt.body = JSON.stringify(body); }
  let res;
  try { res = await fetch(url, opt); } catch { throw new Error("Cannot reach the Story Factory server. Is `python run.py` still running?"); }
  let data = null;
  try { data = await res.json(); } catch { /* not json */ }
  if (res.status === 401 && data && data.login) { location.href = data.login; throw new Error(data.error); }
  if (!res.ok) throw new Error((data && data.error) || `Request failed (${res.status})`);
  return data;
}
export const get = (u) => api("GET", u);
export const post = (u, b) => api("POST", u, b ?? {});
export const put = (u, b) => api("PUT", u, b);
export const patch = (u, b) => api("PATCH", u, b);
export const del = (u) => api("DELETE", u);
