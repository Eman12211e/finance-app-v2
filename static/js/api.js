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
    getDocuments: function () {
      return request("/api/documents");
    },
    getDocument: function (id) {
      return request("/api/documents/" + encodeURIComponent(id));
    },
    getBrokerages: function () {
      return request("/api/brokerages");
    },
    compareBrokerages: function (p) {
      var query = new URLSearchParams({ firms: p.firms.join(","), criteria: p.criteria.join(","), quantity: String(p.quantity) });
      if (p.filters.length) query.set("filters", p.filters.join(","));
      return request("/api/brokerages/compare?" + query.toString());
    },
    postAnalysis: function (body) {
      return request("/api/analysis/indicators", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
    },
    getPaperScenarios: function () {
      return request("/api/paper/scenarios");
    },
    paperPost: function (action, body) {
      return request("/api/paper/" + action, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
    },
    getLabConfig: function () {
      return request("/api/lab/config");
    },
    postLabCompare: function (body) {
      return request("/api/lab/compare", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
    },
  };
})();
