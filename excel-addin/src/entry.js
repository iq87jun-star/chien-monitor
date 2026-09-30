// Excel が読み込むスクリプト(dist/functions.js)の入口。関数を Excel に登録する。
// 読めない値などのエラーは、理由つきの #VALUE! としてセルに返す。
/* global CustomFunctions */
import { FUNCTIONS } from "./functions.js";

for (const f of FUNCTIONS) {
  CustomFunctions.associate(f.name, (...args) => {
    try {
      return f.fn(...args);
    } catch (e) {
      throw new CustomFunctions.Error(
        CustomFunctions.ErrorCode.invalidValue,
        e && e.message ? e.message : String(e),
      );
    }
  });
}
