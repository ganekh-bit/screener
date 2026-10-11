module.exports = {
  version: "7.0",
  title: "Stock Screener",
  description: "Custom stock screener with real-time data from Yahoo Finance",
  menu: async (kernel, info) => {
    const installed = info.exists("app/env")
    const running = {
      install: info.running("install.js"),
      start:   info.running("start.js"),
      update:  info.running("update.js"),
      reset:   info.running("reset.js"),
    }

    if (running.install) {
      return [{
        default: true,
        icon: "fa-solid fa-plug",
        text: "Installing",
        href: "install.js",
      }]
    }

    if (running.update) {
      return [{
        default: true,
        icon: "fa-solid fa-rotate",
        text: "Updating",
        href: "update.js",
      }]
    }

    if (running.reset) {
      return [{
        default: true,
        icon: "fa-solid fa-trash",
        text: "Resetting",
        href: "reset.js",
      }]
    }

    if (installed) {
      if (running.start) {
        const local = info.local("start.js")
        if (local && local.url) {
          return [
            {
              default: true,
              icon: "fa-solid fa-chart-line",
              text: "Open Stock Screener",
              href: local.url,
            },
            {
              icon: "fa-solid fa-terminal",
              text: "Terminal",
              href: "start.js",
            },
          ]
        }
        return [{
          default: true,
          icon: "fa-solid fa-terminal",
          text: "Starting...",
          href: "start.js",
        }]
      }

      return [
        {
          default: true,
          icon: "fa-solid fa-power-off",
          text: "Start",
          href: "start.js",
        },
        {
          icon: "fa-solid fa-rotate",
          text: "Update",
          href: "update.js",
        },
        {
          icon: "fa-solid fa-plug",
          text: "Install",
          href: "install.js",
        },
        {
          icon: "fa-regular fa-circle-xmark",
          text: "Reset",
          href: "reset.js",
        },
      ]
    }

    return [{
      default: true,
      icon: "fa-solid fa-plug",
      text: "Install",
      href: "install.js",
    }]
  }
}
