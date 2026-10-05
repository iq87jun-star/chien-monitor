// リッジ回帰(log(売値) を特徴量の一次式で当てる)。依存なしで学習と予測をする。

// (XᵀX + λI) w = Xᵀy をコレスキー分解で解く(切片には罰則をかけない)
export function fitRidge(X, y, lambda) {
  const d = X[0].length;
  const A = Array.from({ length: d }, () => new Float64Array(d));
  const b = new Float64Array(d);
  for (let r = 0; r < X.length; r++) {
    const x = X[r];
    for (let i = 0; i < d; i++) {
      if (!x[i]) continue;
      b[i] += x[i] * y[r];
      for (let j = 0; j < d; j++) if (x[j]) A[i][j] += x[i] * x[j];
    }
  }
  for (let i = 1; i < d; i++) A[i][i] += lambda;
  A[0][0] += 1e-9;
  // コレスキー分解 A = L Lᵀ
  const L = Array.from({ length: d }, () => new Float64Array(d));
  for (let i = 0; i < d; i++) {
    for (let j = 0; j <= i; j++) {
      let s = A[i][j];
      for (let k = 0; k < j; k++) s -= L[i][k] * L[j][k];
      L[i][j] = i === j ? Math.sqrt(Math.max(s, 1e-12)) : s / L[j][j];
    }
  }
  const z = new Float64Array(d);
  for (let i = 0; i < d; i++) {
    let s = b[i];
    for (let k = 0; k < i; k++) s -= L[i][k] * z[k];
    z[i] = s / L[i][i];
  }
  const w = new Float64Array(d);
  for (let i = d - 1; i >= 0; i--) {
    let s = z[i];
    for (let k = i + 1; k < d; k++) s -= L[k][i] * w[k];
    w[i] = s / L[i][i];
  }
  return [...w];
}

export const dot = (w, x) => x.reduce((s, v, i) => s + v * w[i], 0);
