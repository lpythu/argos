# Releasing argospy

Tag **`X.Y.Z`**（不带 `v`）触发 [`.github/workflows/release.yml`](.github/workflows/release.yml)：

1. 校验 tag 与 `pyproject.toml` 一致
2. `uv build` → PyPI `argospy`（Trusted Publishing）

Dash 镜像在 Acahti [`saidc/argos-dash`](https://acahti.saidc.ai/saidc/argos-dash)：`git push origin dev` 跑 `cd.office`。不跟这个 tag。

本机不执行 `uv publish`。

## Everyday

```bash
./scripts/release.sh 0.6.1
git push origin main --tags
```

脚本只改 `argospy` 版本、提交、打 annotated tag。推送后由 Actions 发 PyPI。

## One-time: PyPI Trusted Publishing

不在 GitHub 里存长期 token。绑定一次 OIDC：

1. 仓库 Environment **`pypi`**（Settings → Environments）
2. https://pypi.org/manage/account/publishing/ → **Add a new pending publisher**
   - PyPI project name: `argospy`
   - Owner: `lpythu`
   - Repository: `argos`
   - Workflow: `release.yml`
   - Environment name: `pypi`
3. 第一次成功的 `uv publish` 会创建项目

不要在仓库里放 `UV_PUBLISH_TOKEN`。`uv publish --trusted-publishing always` 只走 OIDC，空 token 会和 trusted publishing 冲突。
