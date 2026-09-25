// vitest setup: mock the global `wx` mini-program runtime (NFR-TEST-03).

export function installWxMock() {
  const store = new Map();
  const calls = { request: [], storage: [] };
  let nextResponse = { statusCode: 200, data: {}, header: {} };
  let responseQueue = [];

  global.wx = {
    __calls: calls,
    __store: store,
    __respond(next) {
      if (Array.isArray(next)) responseQueue = [...next];
      else {
        responseQueue = [];
        nextResponse = next;
      }
    },
    request(options) {
      calls.request.push(options);
      const response = responseQueue.length ? responseQueue.shift() : nextResponse;
      setTimeout(() => options.success(response), 0);
    },
    setStorageSync(key, value) {
      calls.storage.push(["set", key, value]);
      store.set(key, value);
    },
    getStorageSync(key) {
      return store.has(key) ? store.get(key) : "";
    },
    removeStorageSync(key) {
      calls.storage.push(["remove", key]);
      store.delete(key);
    },
    getAccountInfoSync() {
      return { miniProgram: { envVersion: "develop" } };
    },
  };
  return global.wx;
}

export function resetWxMock() {
  delete global.wx;
}
