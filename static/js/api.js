// Owner: Agent B. ONLY file that calls fetch(). Every function resolves to an envelope and never rejects.
(function () {
  "use strict";

  function networkError() {
    return {
      ok: false, data: null, source: null, as_of: null,
      error: { code: "NETWORK_ERROR", message: "Could not reach the server." },
    };
  }

  function request(url, options) {
    return fetch(url, options)
      .then(function (resp) { return resp.json(); })
      .catch(networkError);
  }

  function stockUrl(ticker, part) {
    return "/api/stocks/" + encodeURIComponent(ticker) + "/" + part;
  }

  window.Api = {
    getSnapshot: function (ticker) {
      return request(stockUrl(ticker, "snapshot"));
    },
    getEarnings: function (ticker, profile) {
      var p = profile || {};
      var query = new URLSearchParams({ age_range: p.age_range || "", risk: p.risk || "" });
      return request(stockUrl(ticker, "earnings") + "?" + query.toString());
    },
    postChat: function (body) {
      return request("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
    },
    getAlerts: function (tickers) {
      return request("/api/alerts?" + new URLSearchParams({ tickers: (tickers || []).join(",") }).toString());
    },
    getHealth: function () {
      return request("/api/health");
    },
    getSentimentStatements: function () {
      return request("/api/sentiment/statements");
    },
    postSentiment: function (statementId) {
      return request("/api/sentiment", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ statement_id: statementId }),
      });
    },
  };
})();
