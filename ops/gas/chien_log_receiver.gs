/**
 * Q111(docs/327): EA(VPS)からの HTTPS POST を受け、Drive の chien_ops/<口座>/vps_log_YYYY-MM.csv に追記する Google Apps Script。
 *
 * 配置(1 回だけ・ご自身の Google アカウントで):
 *   1. https://script.google.com → 新しいプロジェクト → このファイルの中身を Code.gs に貼る → FOLDER_ID を確認(chien_ops のフォルダ ID)。
 *   2. デプロイ → 新しいデプロイ → 種類「ウェブアプリ」→ 実行ユーザー「自分」・アクセス「全員」→ デプロイ → 表示された
 *      https://script.google.com/macros/s/.../exec をコピー(これが InpLogUrl。公開リポジトリには書かない)。
 *   3. 動作確認: ブラウザでその URL を開くと {"ok":true,"ping":...} が返る。
 *   4. 各端末: ツール→オプション→エキスパート「WebRequest を許可する URL」に https://script.google.com と
 *      https://script.googleusercontent.com を追加 → 記録版 EA を付け InpLogUrl に貼る → VPS→移行。
 *
 * 受信形式(1 行 1 レコード・CSV): account,utc,server_time,kind,ea,text   (kind = LOG/SNAP/DEAL/INIT/DEINIT)
 * 書き込み先: chien_ops/<account>/vps_log_<YYYY-MM>.csv(無ければ作成・ヘッダ付き)。
 */
var FOLDER_ID = '1pka7tvg2II5r8mdvFB4cgNqO6yvmPN1y';   // Drive の chien_ops
var HEADER = 'account,utc,server_time,kind,ea,text\n';

function doGet(e) {
  return ContentService.createTextOutput(JSON.stringify({ ok: true, ping: new Date().toISOString() })).setMimeType(ContentService.MimeType.JSON);
}

function doPost(e) {
  var body = (e && e.postData && e.postData.contents) ? e.postData.contents : '';
  var lines = body.split('\n').filter(function (l) { return l.trim().length > 0; });
  if (lines.length === 0) return out({ ok: false, error: 'empty' });
  var byAcct = {};
  lines.forEach(function (l) {
    var m = l.match(/^(\d{4,12}),/);          // 先頭の口座番号
    var acct = m ? m[1] : 'unknown';
    (byAcct[acct] = byAcct[acct] || []).push(l);
  });
  var lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try {
    var root = DriveApp.getFolderById(FOLDER_ID);
    var month = Utilities.formatDate(new Date(), 'UTC', 'yyyy-MM');
    Object.keys(byAcct).forEach(function (acct) {
      var folder = subfolder(root, acct);
      var name = 'vps_log_' + month + '.csv';
      var it = folder.getFilesByName(name);
      var text = byAcct[acct].join('\n') + '\n';
      if (it.hasNext()) {
        var f = it.next();
        f.setContent(f.getBlob().getDataAsString('UTF-8') + text);
      } else {
        folder.createFile(name, HEADER + text, 'text/csv');
      }
    });
  } finally {
    lock.releaseLock();
  }
  return out({ ok: true, n: lines.length });
}

function subfolder(root, name) {
  var it = root.getFoldersByName(name);
  return it.hasNext() ? it.next() : root.createFolder(name);
}

function out(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}
