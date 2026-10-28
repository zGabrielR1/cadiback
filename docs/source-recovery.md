# Export and recover current source

From the Operator directory, run:

```sh
python scripts/export_source.py /tmp/operator-source-YYYYMMDD.zip
```

Choose a new filename each time. The command includes existing tracked files and
untracked files that Git does not ignore, using their current contents rather
than their last committed versions. Deleted files stay deleted. It verifies each
archived file against the embedded SHA-256 manifest after writing the ZIP.

Copy the ZIP to a separate device or storage location for durable recovery.
An archive on the same machine is only a local recovery copy.

Extract into a new directory. The `operator/` folder contains source; the sibling
`SOURCE-MANIFEST.json` records hashes. Reinstall dependencies from lockfiles and
follow the normal project setup instructions. Restore credentials separately.

The exporter skips common credential filenames, local environment files (except
example/template files), symlinks, runtime databases and demo data, dependency and
build folders, selected design evidence, and existing archives. These filename
filters cannot identify secrets embedded in source: review contents before
sharing. Ignored custom source must be explicitly made Git-visible to be included.
This does not preserve Git history, accounts, wallets, databases, or deployment
configuration secrets, and it does not publish or upload anything.
