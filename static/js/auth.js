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
  const loginButton = loginForm
    ? loginForm.querySelector('button[type="submit"]')
    : null;
  let loginRetryTimer = null;

  const next = new URLSearchParams(location.search).get("next") || "/";

  function setError(target, message) {
    if (target) target.textContent = message || "";
  }

  function formatRetry(seconds) {
    const total = Math.max(Number.parseInt(seconds || 0, 10), 0);
    if (total >= 60) {
      const minutes = Math.floor(total / 60);
      const rest = total % 60;
      return rest ? `${minutes} 分 ${rest} 秒` : `${minutes} 分钟`;
    }
    return `${total} 秒`;
  }

  function clearLoginRetryTimer() {
    if (loginRetryTimer) {
      window.clearInterval(loginRetryTimer);
      loginRetryTimer = null;
    }
  }

  function setLoginError(err) {
    let message = err && err.message ? err.message : "";
    if (Number.isFinite(err && err.attemptsRemaining) && err.attemptsRemaining >= 0 && err.status !== 429) {
      message = `${message}，还剩 ${err.attemptsRemaining} 次机会`;
    }
    clearLoginRetryTimer();
    if (err && err.status === 429 && err.retryAfter > 0 && loginButton) {
      let remaining = err.retryAfter;
      loginButton.disabled = true;
      const tick = () => {
        setError(loginError, `${message}，${formatRetry(remaining)} 后可重试`);
        if (remaining <= 0) {
          clearLoginRetryTimer();
          loginButton.disabled = false;
          setError(loginError, "可以重新尝试登录。");
        }
        remaining -= 1;
      };
      tick();
      loginRetryTimer = window.setInterval(tick, 1000);
      return;
    }
    if (loginButton) loginButton.disabled = false;
    setError(loginError, message);
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
      const err = new Error(message);
      err.status = resp.status;
      err.retryAfter = Number.parseInt(data.retry_after || 0, 10);
      err.attemptsRemaining = Number.parseInt(data.attempts_remaining, 10);
      err.maxAttempts = Number.parseInt(data.max_attempts, 10);
      err.resetAt = Number.parseInt(data.reset_at || 0, 10);
      throw err;
    }
    return data;
  }

  if (loginForm) {
    const rememberWrap = loginForm.querySelector("[data-auth-remember]");
    const rememberCheck = loginForm.querySelector("[data-auth-remember-check]");
    const rememberPanel = loginForm.querySelector("[data-auth-remember-panel]");

    const syncRememberPanel = () => {
      if (!rememberWrap || !rememberCheck) return;
      rememberWrap.classList.toggle("is-open", rememberCheck.checked);
      if (!rememberCheck.checked && rememberPanel) {
        rememberPanel.scrollTop = 0;
      }
    };

    if (rememberCheck) {
      rememberCheck.addEventListener("change", syncRememberPanel);
      syncRememberPanel();
    }

    loginForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const form = new FormData(loginForm);
      const payload = {
        username: form.get("username"),
        password: form.get("password"),
      };
      const shouldRemember = rememberCheck
        ? rememberCheck.checked
        : form.get("remember_device") === "1";
      if (shouldRemember) {
        const selected = loginForm.querySelector('input[name="session_days"]:checked');
        const sessionDays = Number.parseInt(selected ? selected.value : "", 10);
        if (Number.isFinite(sessionDays)) {
          payload.session_days = sessionDays;
        }
      }
      try {
        await fetchJSON("/auth/login", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        markLoggedIn();
        location.assign(next);
      } catch (err) {
        setLoginError(err);
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
        const loginNext = `?next=${encodeURIComponent(next)}`;
        location.assign(`/auth/login/${loginNext}`);
      } catch (err) {
        setError(registerError, err.message);
      }
    });
  }
})();
