# 0093 — Local source recovery export

The owner reported losing access to files in other projects and asked to continue
Operator using the shared automation prompts. This working tree contains current
uncommitted source, so a commit-only archive would omit important work.

Provide a stdlib ZIP exporter using Git's tracked and nonignored untracked paths,
reading current contents and omitting deleted paths. Filter common private and
generated artifacts, omit symlinks, preserve file mode metadata, and include
SHA-256 hashes checked by reading the completed ZIP. Refuse existing destinations
and destinations inside the source tree.

This is source recovery only. It is not an off-machine backup, secret scanner,
Git history backup, database backup, or deployment. Document these boundaries and
keep existing working tree changes intact.
