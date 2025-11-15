import { jsx as t, jsxs as b } from "react/jsx-runtime";
import v from "axios";
import { useState as w, useMemo as O, useEffect as E } from "react";
const C = {}, T = "http://localhost:4433", V = T, A = () => C?.VITE_ORY_BROWSER_URL?.replace(/\/$/, "") || T, x = () => C?.VITE_ORY_PUBLIC_API_URL?.replace(/\/$/, "") || V, B = (n) => {
  const o = C;
  return n === "login" ? o?.VITE_AUTH_LOGIN_REDIRECT || o?.VITE_AUTH_SUCCESS_REDIRECT || "/" : n === "registration" ? o?.VITE_AUTH_REGISTRATION_REDIRECT || o?.VITE_AUTH_SUCCESS_REDIRECT || "/" : o?.VITE_AUTH_RECOVERY_REDIRECT || o?.VITE_AUTH_SUCCESS_REDIRECT || "/login";
}, p = (n, o) => {
  const c = A();
  if (typeof window > "u") return;
  const u = new URL(`${c}/self-service/${n}/browser`);
  o && u.searchParams.set("return_to", o), window.location.href = u.toString();
}, P = {
  login: "Continue",
  registration: "Create account",
  recovery: "Send recovery link"
}, R = ({
  flowType: n,
  title: o,
  description: c,
  submitLabel: u,
  className: h,
  redirectTo: y,
  footer: d,
  onError: f,
  onSuccess: m
}) => {
  const [l, S] = w(null), [$, U] = w(!0), [I, L] = w({}), [N, _] = w(null), k = O(() => A(), []);
  E(() => {
    if (typeof window > "u") return;
    let a = !1;
    return (async () => {
      U(!0), _(null);
      try {
        const r = new URLSearchParams(window.location.search).get("flow");
        if (!r) {
          p(n, window.location.href);
          return;
        }
        const s = await v.get(`${k}/self-service/${n}/flows`, {
          params: { id: r },
          withCredentials: !0
        });
        a || S(s.data);
      } catch (i) {
        if (console.error(`Failed to load ${n} flow`, i), i?.response?.status === 404 || i?.response?.status === 410) {
          p(n, window.location.href);
          return;
        }
        _("Unable to reach the Ory backend. Check your env values."), f?.(i);
      } finally {
        a || U(!1);
      }
    })(), () => {
      a = !0;
    };
  }, [k, n, f]), E(() => {
    l && L((a) => {
      const e = { ...a };
      return l.ui.nodes.forEach((i) => {
        const { name: r, value: s } = i.attributes;
        s !== void 0 && e[r] === void 0 && (e[r] = String(s));
      }), e;
    });
  }, [l]);
  const F = (a, e) => {
    L((i) => ({ ...i, [a]: e }));
  }, D = async (a) => {
    if (a.preventDefault(), !l) return;
    const e = new URLSearchParams();
    Object.entries(I).forEach(([r, s]) => {
      e.set(r, s);
    }), l.ui.nodes.filter((r) => r.attributes.type === "hidden").forEach((r) => {
      const { name: s, value: g } = r.attributes;
      !s || g === void 0 || e.has(s) || e.set(s, String(g));
    });
    const i = l.ui.nodes.find((r) => r.attributes.name === "csrf_token");
    if (i && !e.get("csrf_token") && i.attributes.value && e.set("csrf_token", String(i.attributes.value)), !e.get("method")) {
      const r = l.ui.nodes.find((s) => s.attributes.name === "method");
      r?.attributes.value ? e.set("method", String(r.attributes.value)) : n === "login" && e.set("method", "password");
    }
    try {
      const r = await v.post(l.ui.action, e, {
        withCredentials: !0,
        headers: { "Content-Type": "application/x-www-form-urlencoded" }
      });
      if (m) {
        m(r.data);
        return;
      }
      const s = y || B(n);
      s && typeof window < "u" && window.location.assign(s);
    } catch (r) {
      console.error("Auth flow submission failed", r), f?.(r);
      const s = r?.response?.data;
      if (s?.ui) {
        S(s);
        return;
      }
      if (r?.response?.status === 410) {
        p(n, typeof window < "u" ? window.location.href : void 0);
        return;
      }
      _("The credentials were rejected. Please try again.");
    }
  };
  return $ || !l ? /* @__PURE__ */ t("div", { className: `ory-auth-shell ${h ?? ""}`, children: /* @__PURE__ */ t("div", { className: "ory-auth-panel", children: /* @__PURE__ */ b("p", { className: "ory-auth-loading", children: [
    "Loading ",
    n,
    " flow..."
  ] }) }) }) : /* @__PURE__ */ t("div", { className: `ory-auth-shell ${h ?? ""}`, children: /* @__PURE__ */ b("form", { className: "ory-auth-panel", onSubmit: D, children: [
    o && /* @__PURE__ */ t("h2", { className: "ory-auth-title", children: o }),
    c && /* @__PURE__ */ t("p", { className: "ory-auth-description", children: c }),
    N && /* @__PURE__ */ t("p", { className: "ory-auth-error", children: N }),
    l.ui.messages?.length ? /* @__PURE__ */ t("div", { className: "ory-auth-error", children: l.ui.messages.map((a) => /* @__PURE__ */ t("p", { children: a.text }, a.id)) }) : null,
    l.ui.nodes.map((a) => {
      const e = a.attributes, i = `${l.id}-${e.name}`;
      if (e.type === "hidden")
        return /* @__PURE__ */ t("input", { type: "hidden", name: e.name, value: String(e.value ?? "") }, i);
      if (e.type === "submit" || e.type === "button")
        return null;
      const r = a.meta?.label?.text || e.name, s = I[e.name] ?? "";
      return /* @__PURE__ */ b("div", { className: "ory-auth-field", children: [
        /* @__PURE__ */ t("label", { className: "ory-auth-label", htmlFor: e.name, children: r }),
        /* @__PURE__ */ t(
          "input",
          {
            id: e.name,
            name: e.name,
            type: e.name.toLowerCase().includes("email") ? "email" : e.type,
            className: "ory-auth-input",
            placeholder: e.placeholder,
            autoComplete: e.autocomplete,
            disabled: e.disabled,
            required: e.required,
            value: s,
            onChange: (g) => F(e.name, g.target.value)
          }
        ),
        a.messages?.map((g) => /* @__PURE__ */ t("p", { className: "ory-auth-field-message", children: g.text }, g.id))
      ] }, i);
    }),
    /* @__PURE__ */ t("button", { type: "submit", className: "ory-auth-submit", children: u || P[n] }),
    d && /* @__PURE__ */ t("div", { className: "ory-auth-footer", children: d })
  ] }) });
}, H = () => /* @__PURE__ */ b("div", { className: "ory-auth-links", children: [
  /* @__PURE__ */ t("button", { type: "button", onClick: () => p("registration"), children: "Create account" }),
  /* @__PURE__ */ t("button", { type: "button", onClick: () => p("recovery"), children: "Forgot password?" })
] }), z = ({
  title: n = "Sign in",
  description: o = "Enter your credentials to continue with your subscription.",
  submitLabel: c = "Continue",
  footer: u,
  ...h
}) => /* @__PURE__ */ t(
  R,
  {
    flowType: "login",
    title: n,
    description: o,
    submitLabel: c,
    footer: u ?? /* @__PURE__ */ t(H, {}),
    ...h
  }
), j = () => /* @__PURE__ */ b("div", { className: "ory-auth-links", children: [
  /* @__PURE__ */ t("button", { type: "button", onClick: () => p("login"), children: "Already have an account?" }),
  /* @__PURE__ */ t("button", { type: "button", onClick: () => p("recovery"), children: "Recover access" })
] }), J = ({
  title: n = "Create your account",
  description: o = "Provision access to the shared Ory identity platform.",
  submitLabel: c = "Create account",
  footer: u,
  ...h
}) => /* @__PURE__ */ t(
  R,
  {
    flowType: "registration",
    title: n,
    description: o,
    submitLabel: c,
    footer: u ?? /* @__PURE__ */ t(j, {}),
    ...h
  }
), q = () => /* @__PURE__ */ b("div", { className: "ory-auth-links", children: [
  /* @__PURE__ */ t("button", { type: "button", onClick: () => p("login"), children: "Back to login" }),
  /* @__PURE__ */ t("button", { type: "button", onClick: () => p("registration"), children: "Need an account?" })
] }), K = ({
  title: n = "Recover access",
  description: o = "Send yourself a magic link to reset your password.",
  submitLabel: c = "Send recovery link",
  footer: u,
  ...h
}) => /* @__PURE__ */ t(
  R,
  {
    flowType: "recovery",
    title: n,
    description: o,
    submitLabel: c,
    footer: u ?? /* @__PURE__ */ t(q, {}),
    ...h
  }
), W = () => {
  const [n, o] = w(null), [c, u] = w(!0), [h, y] = w(null);
  return E(() => {
    let d = !0;
    return (async () => {
      try {
        const m = x(), l = await v.get(`${m}/sessions/whoami`, {
          withCredentials: !0
        });
        if (!d) return;
        o(l.data), y(null);
      } catch (m) {
        if (!d) return;
        v.isAxiosError(m) && (m.response?.status === 401 || m.response?.status === 403) ? (o(null), y(null)) : (o(null), y(m));
      } finally {
        d && u(!1);
      }
    })(), () => {
      d = !1;
    };
  }, []), { session: n, loading: c, error: h };
}, Q = ({
  children: n,
  redirectTo: o = "/login",
  loadingFallback: c,
  skipRedirect: u = !1
}) => {
  const { session: h, loading: y } = W();
  if (y)
    return c ?? /* @__PURE__ */ t("p", { children: "Checking session..." });
  if (!h && !u) {
    const d = o ?? "/login";
    let f;
    return /^https?:\/\//i.test(d) ? f = d : d.startsWith("/") ? f = `${window.location.origin}${d}` : f = `${window.location.origin}/${d}`, window.location.href = f, null;
  }
  return n;
};
export {
  R as AuthFlow,
  z as Login,
  K as Recovery,
  J as Registration,
  Q as RequireAuth,
  A as getOryBrowserUrl,
  x as getOryPublicApiBaseUrl,
  B as getRedirectUrl,
  p as openOryBrowserFlow,
  W as useSession
};
//# sourceMappingURL=index.js.map
