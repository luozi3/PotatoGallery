(function () {
  const root = document.body;
  const requireHttps = root && root.dataset.authRequireHttps === "1";
  const isLocalhost =
    location.hostname === "localhost" || location.hostname === "127.0.0.1";
  if (requireHttps && location.protocol !== "https:" && !isLocalhost) {
    location.replace(`https://${location.host}${location.pathname}${location.search}`);
    return;
  }

  const loginForm = document.querySelector("[data-auth-login-form]");
  const registerForm = document.querySelector("[data-auth-register-form]");
  const loginError = document.querySelector("[data-auth-login-error]");
  const registerError = document.querySelector("[data-auth-register-error]");

  const next = new URLSearchParams(location.search).get("next") || "/";

  function setError(target, message) {
    if (target) target.textContent = message || "";
  }

  function markLoggedIn() {
    try {
      localStorage.setItem("auth-hint", "1");
      document.documentElement.classList.add("auth-hint-logged-in");
    } catch (e) {}
  }

  async function fetchJSON(url, options) {
    const resp = await fetch(url, { credentials: "include", ...options });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) {
      const message = data.error || "请求失败";
      throw new Error(message);
    }
    return data;
  }

  if (loginForm) {
    loginForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const form = new FormData(loginForm);
      const payload = {
        username: form.get("username"),
        password: form.get("password"),
      };
      try {
        await fetchJSON("/auth/login", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        markLoggedIn();
        location.assign(next);
      } catch (err) {
        setError(loginError, err.message);
      }
    });
  }

  if (registerForm) {
    registerForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const form = new FormData(registerForm);
      const password = form.get("password") || "";
      const passwordConfirm = form.get("password_confirm") || "";
      if (!passwordConfirm) {
        setError(registerError, "请再次输入密码");
        return;
      }
      if (password !== passwordConfirm) {
        setError(registerError, "两次密码不一致");
        return;
      }
      const payload = {
        username: form.get("username"),
        password,
        password_confirm: passwordConfirm,
        invite_code: form.get("invite_code"),
      };
      try {
        await fetchJSON("/auth/register", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        markLoggedIn();
        location.assign(next);
      } catch (err) {
        setError(registerError, err.message);
      }
    });
  }
})();
