---
tool: kubeconform
scope: k8s
tier: baseline
summary: "Schema-validate K8s manifests in CI against K8s + CRD schemas"
targets: [".gitlab-ci.yml"]
detect_content: ["^kind:\\s"]
platform: any
---

# kubeconform

## What

[kubeconform](https://github.com/yannh/kubeconform) validates Kubernetes manifests
against the upstream Kubernetes OpenAPI schemas and any CRD schemas you point it at. It
is the *type-checker* for a manifest repo: a bad `apiVersion`, a misspelled field, a
wrong type — caught in CI before Argo CD (or `kubectl apply`) ever sees it. Pairs with
[yamllint](./yamllint.md): yamllint proves the YAML is well-formed, kubeconform proves
the resource is real.

## Why

- **A GitOps merge is a deploy.** With Argo CD / Flux, merging to `main` syncs to the
  cluster — there is no `kubectl apply` review step to catch a typo. kubeconform is that
  step, in CI.
- **CRD coverage via the catalog.** Point `-schema-location` at the
  [datreeio CRDs-catalog](https://github.com/datreeio/CRDs-catalog) and Argo CD,
  External Secrets, Gateway API, cert-manager, etc. all validate too — not just core
  kinds.

## Config

CI-only — kubeconform fetches CRD schemas over the network, so it belongs in the
pipeline, not a commit hook. GitLab job:

```yaml
# Schema-validate Kubernetes manifests so a malformed resource can't reach Argo CD.
# Only files containing `kind:` are checked (skips helm/ values, monitoring/ alerts,
# docs, etc.). CRDs absent from the catalog are soft-skipped.
validate-manifests:
  stage: lint
  image:
    name: ghcr.io/yannh/kubeconform:vX.Y.Z-alpine # pin to latest stable; renovate bumps it
    entrypoint: [""]
  rules:
    - changes: ["**/*.yaml", "**/*.yml"]
  script:
    - |
      find . -type f \( -name '*.yaml' -o -name '*.yml' \) -not -path './.git/*' \
        -exec grep -lE '^kind:' {} + \
        | xargs -r /kubeconform -strict -summary -ignore-missing-schemas \
            -schema-location default \
            -schema-location 'https://raw.githubusercontent.com/datreeio/CRDs-catalog/main/{{.Group}}/{{.ResourceKind}}_{{.ResourceAPIVersion}}.json'
```

Flags that matter: `-strict` (reject unknown fields), `-ignore-missing-schemas` (don't
fail on a CRD the catalog lacks — see Gotchas), `-summary` (one-line totals),
`-schema-location default` (the bundled K8s schemas) plus the catalog URL.

### Helm / Kustomize — render first

kubeconform validates *plain* manifests. A Helm chart's `templates/*.yaml` or a
Kustomize overlay is not valid YAML until rendered, so pipe the rendered output in:

```bash
helm template . | kubeconform -strict -ignore-missing-schemas -schema-location default ...
kustomize build . | kubeconform -strict -ignore-missing-schemas -schema-location default ...
```

(The `grep '^kind:'` selection above is for repos of already-plain manifests, like an
Argo CD GitOps repo.)

For Kustomize overlay repos in GitLab CI, split into a two-stage pipeline so rendered overlays are archived and inspected directly:

```yaml
render-manifests:
  stage: render
  image:
    name: registry.k8s.io/kustomize/kustomize:vX.Y.Z # pin to latest stable; renovate bumps it
    entrypoint: [""]
  script:
    - mkdir -p rendered
    - |
      for f in $(find . -name kustomization.yaml -not -path './base/*'); do
        dir=$(dirname "$f")
        name=$(echo "$dir" | tr '/' '_' | sed 's/^\._//')
        kustomize build --load-restrictor LoadRestrictionsNone "$dir" > "rendered/${name}.yaml"
      done
  artifacts:
    paths: [rendered/]

validate-manifests:
  stage: lint
  needs: ["render-manifests"]
  image:
    name: ghcr.io/yannh/kubeconform:vX.Y.Z-alpine # pin to latest stable; renovate bumps it
    entrypoint: [""]
  script:
    - /kubeconform -strict -summary -ignore-missing-schemas -schema-location default -schema-location 'https://raw.githubusercontent.com/datreeio/CRDs-catalog/main/{{.Group}}/{{.ResourceKind}}_{{.ResourceAPIVersion}}.json' rendered/*.yaml
```

### Image tag existence check

Extract `image:` references from rendered manifests and verify each digest exists in the registry with `crane digest` so missing tags fail the MR before Argo CD hits `ImagePullBackOff`:

```bash
grep -hE '^\s*image:\s*' rendered/*.yaml | awk '{print $2}' | tr -d '"'"'" | sort -u | while read -r img; do
  crane digest "$img" >/dev/null
done
```

## Gotchas

- **The binary lives at `/kubeconform`, not on `PATH`.** The official image's entrypoint
  *is* kubeconform; once you override `entrypoint: [""]` to run a shell pipeline, a bare
  `kubeconform` is "not found". Call it by absolute path: `/kubeconform`.
- **`-ignore-missing-schemas` is load-bearing for custom CRDs.** Vendor CRDs not in the
  catalog (e.g. GKE's `networking.gke.io` `GCPBackendPolicy` / `HealthCheckPolicy`)
  have no schema; without this flag the job fails on them. With it they're soft-skipped
  (reported, not failed). Check the `Skipped:` count in the summary so you know what
  *isn't* being validated.
- **Not a policy check.** kubeconform validates schema only (no runAsNonRoot, no resource limits). Add kube-linter or conftest for policy.
