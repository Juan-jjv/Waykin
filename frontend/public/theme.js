// Loaded as a file, not inline: the server's CSP only allows same-origin scripts.
(function () {
  try {
    var saved = localStorage.getItem("waykin:appearance");
    var theme =
      saved === "light" || saved === "dark"
        ? saved
        : window.matchMedia("(prefers-color-scheme: dark)").matches
          ? "dark"
          : "light";
    document.documentElement.setAttribute("data-theme", theme);
  } catch (err) {
    document.documentElement.setAttribute("data-theme", "light");
  }
})();
