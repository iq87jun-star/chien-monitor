// メニューと使い方の画面(エディタのアドオン)。関数そのものは functions.js。

/* global SpreadsheetApp, HtmlService */

function onInstall(e) {
  onOpen(e);
}

function onOpen() {
  SpreadsheetApp.getUi().createAddonMenu().addItem("使い方(関数の一覧)", "showHelp").addToUi();
}

function showHelp() {
  var html = HtmlService.createHtmlOutputFromFile("Help").setTitle("日本の計算関数");
  SpreadsheetApp.getUi().showSidebar(html);
}
