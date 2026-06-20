(function () {
  'use strict';

  // 按句末、空行、Markdown 标题前拆段，避免合并时丢失换行
  const UNIT_SPLIT = /(?<=[。！？.!?])\s*|\n+(?=#{1,6}\s)|\n{2,}/;

  function splitUnits(text) {
    if (!text) return [];
    return text.split(UNIT_SPLIT).map(s => s.trim()).filter(Boolean);
  }

  function charsToText(encoded, lineArray) {
    let out = '';
    for (let i = 0; i < encoded.length; i++) {
      const idx = encoded.charCodeAt(i);
      if (idx >= lineArray.length - 1) continue;
      const line = lineArray[idx];
      if (!line) continue;
      if (out) out += '\n';
      out += line;
    }
    return out;
  }

  function expandDiffs(diffs, lineArray) {
    return diffs.map(([op, chars]) => [op, charsToText(chars, lineArray)]);
  }

  function sentencesToChars(text1, text2) {
    const lineArray = [];
    const lineHash = Object.create(null);

    function encode(text) {
      let chars = '';
      const units = splitUnits(text);
      for (let i = 0; i < units.length; i++) {
        const line = units[i];
        if (lineHash[line] === undefined) {
          lineHash[line] = lineArray.length;
          lineArray.push(line);
        }
        chars += String.fromCharCode(lineHash[line]);
      }
      chars += String.fromCharCode(lineArray.length);
      lineArray.push('');
      return chars;
    }

    return {
      chars1: encode(text1),
      chars2: encode(text2),
      lineArray
    };
  }

  function computeDiff(oldText, newText) {
    const dmp = new diff_match_patch();
    const encoded = sentencesToChars(oldText, newText);
    const diffs = dmp.diff_main(encoded.chars1, encoded.chars2, false);
    dmp.diff_cleanupSemantic(diffs);
    return groupHunks(expandDiffs(diffs, encoded.lineArray));
  }

  function groupHunks(diffs) {
    const hunks = [];
    let i = 0;
    while (i < diffs.length) {
      const [op, text] = diffs[i];
      if (op === 0) {
        hunks.push({ type: 'equal', text, id: 'h' + hunks.length });
        i++;
        continue;
      }
      const dels = [];
      const ins = [];
      while (i < diffs.length && diffs[i][0] === -1) { dels.push(diffs[i][1]); i++; }
      while (i < diffs.length && diffs[i][0] === 1) { ins.push(diffs[i][1]); i++; }
      const oldText = dels.join('\n');
      const newText = ins.join('\n');
      if (oldText && newText) {
        hunks.push({ type: 'change', oldText, newText, id: 'h' + hunks.length });
      } else if (newText) {
        hunks.push({ type: 'add', newText, id: 'h' + hunks.length });
      } else if (oldText) {
        hunks.push({ type: 'remove', oldText, id: 'h' + hunks.length });
      }
    }
    return hunks;
  }

  function defaultDecisions(hunks) {
    const d = {};
    hunks.forEach(h => {
      if (h.type === 'equal') d[h.id] = { choice: 'equal', text: h.text };
      else if (h.type === 'change' || h.type === 'add') d[h.id] = { choice: 'new', text: h.newText };
      else if (h.type === 'remove') d[h.id] = { choice: 'remove', text: '' };
    });
    return d;
  }

  function buildMergedText(hunks, decisions) {
    return hunks.map(h => {
      const dec = decisions[h.id];
      if (!dec) {
        if (h.type === 'equal') return h.text;
        if (h.type === 'change' || h.type === 'add') return h.newText;
        return '';
      }
      if (dec.choice === 'equal') return h.text;
      if (dec.choice === 'old') return h.oldText || '';
      if (dec.choice === 'new') return h.newText || dec.text || '';
      if (dec.choice === 'remove') return '';
      if (dec.choice === 'custom') return dec.text || '';
      return '';
    }).filter(Boolean).join('\n');
  }

  function pushVersion(session, content, label, opts) {
    if (!content || !content.trim()) return null;
    if (!session.prdVersions) session.prdVersions = [];
    const last = session.prdVersions[session.prdVersions.length - 1];
    if (last && last.content === content && (!opts || opts.allowDuplicate !== true)) return last;
    const v = session.prdVersions.length + 1;
    const entry = {
      v, content, createdAt: Date.now(),
      label: label || ('v' + v),
      confirmed: opts && opts.confirmed === false ? false : true
    };
    session.prdVersions.push(entry);
    return entry;
  }

  function confirmVersion(session, v, content, label) {
    if (!content || !content.trim()) return null;
    if (!session.prdVersions) session.prdVersions = [];
    const entry = session.prdVersions.find(x => x.v === v);
    if (!entry) return pushVersion(session, content, label);
    entry.content = content;
    entry.confirmed = true;
    entry.confirmedAt = Date.now();
    if (label) entry.label = label;
    return entry;
  }

  function getVersion(session, v) {
    return (session.prdVersions || []).find(x => x.v === v);
  }

  window.PrdForge = window.PrdForge || {};
  PrdForge.PrdVersions = {
    splitUnits,
    computeDiff,
    defaultDecisions,
    buildMergedText,
    pushVersion,
    confirmVersion,
    getVersion
  };
})();
