# Kubernetes Playbook

Tooling for repos whose product is Kubernetes manifests — plain-YAML GitOps repos
(Argo CD / Flux), and the manifest layer of any app deployed to k8s.

Detection is **content-based** (`detect_content: ["^kind:\\s"]`): a plain-manifest repo
has no marker file like `package.json`, so the resolver keys on YAML bodies containing
`kind:` rather than on a path glob. Helm chart and Kustomize repos match too (their
templates/overlays contain `kind:`) — see the "render first" note in
[kubeconform.md](./kubeconform.md).

## Pages

- [yamllint.md](./yamllint.md) — lint all YAML, tuned for kubectl-style manifests
- [kubeconform.md](./kubeconform.md) — schema-validate manifests in CI (K8s + CRD schemas)

## See also

- [universal/git-ai-instructions.md](../universal/git-ai-instructions.md) — a GitOps repo
  flips commit-type heuristics (every change is a deploy); its worked example covers this.
- [universal/renovate.md](../universal/renovate.md) — tracks Helm chart versions, image
  tags, and the kubeconform CI image.
