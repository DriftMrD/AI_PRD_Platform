(function () {
  'use strict';

  // 按段落（空行）拆段，避免在「4.1」「6.2」等章节序号处误切
  const UNIT_SPLIT = /\n{2,}/;
  const UNIT_GLUE = '\n\n';

  function splitUnits(text) {
    if (!text) return [];
    return text.split(UNIT_SPLIT).map(s => s.trim()).filter(Boolean);
  }

  /** 修复合并误拆的章节号，如「4.」+「1 Figma」或「### 4.」+「1 Figma」 */
  function repairBrokenSectionNumbers(text) {
    if (!text) return text;
    const lines = text.split('\n');
    const out = [];
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      const next = lines[i + 1];
      const trimmed = line.trim();
      if (/^(#{1,6}\s+)?\d+\.\s*$/.test(trimmed) && next != null && /^\d/.test(next.trim())) {
        out.push(trimmed + next.trim());
        i++;
        continue;
      }
      out.push(line);
    }
    return out.join('\n');
  }

  function charsToText(encoded, lineArray) {
    let out = '';
    for (let i = 0; i < encoded.length; i++) {
      const idx = encoded.charCodeAt(i);
      if (idx >= lineArray.length - 1) continue;
      const line = lineArray[idx];
      if (!line) continue;
      if (out) out += UNIT_GLUE;
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
      const oldText = dels.join(UNIT_GLUE);
      const newText = ins.join(UNIT_GLUE);
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
    const parts = hunks.map(h => {
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
    }).filter(part => part != null && part !== '');
    return repairBrokenSectionNumbers(parts.join(UNIT_GLUE));
  }

  function isActiveVersion(ver) {
    return ver && ver.deleted !== 1;
  }

  function isActiveMessage(msg) {
    return msg && msg.deleted !== 1;
  }

  function activeVersions(session) {
    return (session.prdVersions || []).filter(isActiveVersion);
  }

  function activeMessages(session) {
    return (session.messages || []).filter(isActiveMessage);
  }

  function maxVersionNumber(session) {
    const versions = session.prdVersions || [];
    if (!versions.length) return 0;
    return Math.max(...versions.map(x => x.v));
  }

  function latestVersion(session) {
    const list = activeVersions(session);
    return list.length ? list[list.length - 1] : null;
  }

  function lastEffectiveVersion(versions) {
    const list = (versions || []).filter(isActiveVersion);
    for (let i = list.length - 1; i >= 0; i--) {
      if (!list[i].ignored) return list[i].v;
    }
    return list[0]?.v ?? null;
  }

  function pushVersion(session, content, label, opts) {
    if (!content || !content.trim()) return null;
    if (!session.prdVersions) session.prdVersions = [];
    const active = activeVersions(session);
    const last = active[active.length - 1];
    if (last && last.content === content && (!opts || opts.allowDuplicate !== true)) return last;
    const v = maxVersionNumber(session) + 1;
    const entry = {
      v, content, createdAt: Date.now(),
      label: label || ('v' + v),
      confirmed: opts && opts.confirmed === false ? false : true,
      deleted: 0
    };
    if (opts && typeof opts.messageCount === 'number') {
      entry.messageCount = opts.messageCount;
    }
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
    entry.ignored = false;
    entry.deleted = 0;
    delete entry.ignoredAt;
    delete entry.deletedAt;
    if (label) entry.label = label;
    return entry;
  }

  function ignoreVersion(session, v, label) {
    if (!session.prdVersions) session.prdVersions = [];
    const entry = session.prdVersions.find(x => x.v === v);
    if (!entry) return null;
    entry.ignored = true;
    entry.confirmed = false;
    entry.ignoredAt = Date.now();
    entry.label = label || ((entry.label || 'v' + v).replace(/（已忽略）$/, '') + '（已忽略）');
    return entry;
  }

  function getVersion(session, v) {
    return (session.prdVersions || []).find(x => x.v === v && isActiveVersion(x));
  }

  function resolveMessageCutoff(messages, targetV, versionEntry) {
    if (typeof versionEntry?.messageCount === 'number') {
      return versionEntry.messageCount;
    }
    for (let i = messages.length - 1; i >= 0; i--) {
      const m = messages[i];
      if (m.role !== 'assistant') continue;
      if (m.content.includes('v' + targetV)) return i + 1;
    }
    if (versionEntry?.label?.includes('手动编辑')) return messages.length;
    if (targetV === 1) {
      const firstUser = messages.findIndex(m => m.role === 'user');
      if (firstUser < 0) return messages.length;
      let end = firstUser;
      if (messages[end + 1]?.role === 'assistant') end++;
      return end + 1;
    }
    return messages.length;
  }

  function softDeleteMessagesFrom(messages, cutoff) {
    messages.forEach((m, i) => {
      if (i >= cutoff) m.deleted = 1;
    });
  }

  /** 回退到指定版本：标记其后版本与对话为 deleted=1，不物理删除。 */
  function rollbackToVersion(session, targetV) {
    const versions = session.prdVersions || [];
    const target = versions.find(x => x.v === targetV);
    if (!target || !isActiveVersion(target)) return null;

    const latest = latestVersion(session);
    if (!latest || targetV >= latest.v) return null;

    const removedVersions = [];
    versions.forEach(ver => {
      if (ver.v > targetV && isActiveVersion(ver)) {
        ver.deleted = 1;
        ver.deletedAt = Date.now();
        removedVersions.push(ver);
      }
    });

    target.ignored = false;
    target.confirmed = true;
    target.deleted = 0;
    delete target.ignoredAt;
    delete target.deletedAt;

    session.prd = target.content;
    const messages = session.messages || [];
    const cutoff = resolveMessageCutoff(messages, targetV, target);
    softDeleteMessagesFrom(messages, cutoff);

    session.updatedAt = Date.now();
    return { target, removedVersions };
  }

  window.PrdForge = window.PrdForge || {};
  PrdForge.PrdVersions = {
    splitUnits,
    repairBrokenSectionNumbers,
    computeDiff,
    defaultDecisions,
    buildMergedText,
    isActiveVersion,
    isActiveMessage,
    activeVersions,
    activeMessages,
    latestVersion,
    lastEffectiveVersion,
    pushVersion,
    confirmVersion,
    ignoreVersion,
    rollbackToVersion,
    getVersion
  };
})();
