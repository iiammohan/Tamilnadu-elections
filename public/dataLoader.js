/* === Candidate Data Loader ===
 *  Fetches enriched candidate JSON produced by the Python ETL pipeline.
 *  Falls back gracefully if the files don't exist (site works as before).
 */

const CandidateData = (() => {
  let _byAC = null;   // { "1": [ {…}, … ], "2": [...] }
  let _all = null;     // [ {…}, … ]
  let _summary = null; // { total_candidates, … }
  let _loaded = false;
  let _loading = null; // promise

  async function _fetch(path) {
    try {
      const resp = await fetch(path);
      if (!resp.ok) return null;
      return await resp.json();
    } catch {
      return null;
    }
  }

  async function load() {
    if (_loaded) return true;
    if (_loading) return _loading;
    _loading = (async () => {
      const [byAC, all, summary] = await Promise.all([
        _fetch('data/tn2026_by_constituency.json'),
        _fetch('data/tn2026_all_candidates.json'),
        _fetch('data/tn2026_summary.json'),
      ]);
      _byAC = byAC;
      _all = all;
      _summary = summary;
      _loaded = !!(_byAC || _all);
      return _loaded;
    })();
    return _loading;
  }

  function isAvailable() { return _loaded; }

  function getByAC(acNo) {
    if (!_byAC) return [];
    return _byAC[String(acNo)] || [];
  }

  function getAll() { return _all || []; }
  function getSummary() { return _summary; }

  function formatCurrency(val) {
    if (val == null) return '—';
    if (val >= 1e7) return '₹' + (val / 1e7).toFixed(2) + ' Cr';
    if (val >= 1e5) return '₹' + (val / 1e5).toFixed(2) + ' L';
    if (val >= 1e3) return '₹' + (val / 1e3).toFixed(1) + ' K';
    return '₹' + val.toLocaleString('en-IN');
  }

  return { load, isAvailable, getByAC, getAll, getSummary, formatCurrency };
})();
