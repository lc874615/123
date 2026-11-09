// Compatibility shim: image collection never dispatches follow-up generation.
(()=>{globalThis.OzonImageRetry={maybe:async()=>false};})();
