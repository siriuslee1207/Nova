// 音韻拆解（對應 nova_core/yinyun.py）。字典拼音已由 ETL 轉為數字調（hao4）；輕聲無數字，tone() 回 0。
(function (Nova) {
  'use strict';
  const SHENGMU = ['zh', 'ch', 'sh', 'b', 'p', 'm', 'f', 'd', 't', 'n', 'l', 'g', 'k', 'h',
    'j', 'q', 'x', 'z', 'c', 's', 'r', 'y', 'w'];

  function tone(py) {
    const last = py ? py[py.length - 1] : '';
    return last >= '1' && last <= '4' ? Number(last) : 0;
  }
  function base(py) {
    return py && /[0-9]$/.test(py) ? py.slice(0, -1) : py;
  }
  function shengmu(py) {
    const b = base(py);
    for (const sm of SHENGMU) if (b.startsWith(sm)) return sm;
    return '';
  }
  function yunmu(py) {
    const b = base(py);
    return b.slice(shengmu(py).length);
  }

  Nova.yinyun = { SHENGMU, tone, base, shengmu, yunmu };
})(globalThis.Nova = globalThis.Nova || {});
