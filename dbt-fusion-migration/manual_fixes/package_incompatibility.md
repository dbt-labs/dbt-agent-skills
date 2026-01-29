# Package incompatibility

## PROBLEM

Fusion cannot parse (`dbtf parse`) a user project if the project itself is not compatilbe with the authoring layer.

## SOLUTION

Upgrade any packages with known error to the latest version wherever possible.

to do upgrade a package look up the latest version on https://hub.getdbt.com/

then modify either one of these files:
- `dependencies.yml`
- `packages.yml`

Rather than providing just the newest version, you should provide a compatibility range where so that patches can automaticall be included

```
  - package: fivetran/social_media_reporting
    # not this
    version: 1.0.0
    # this
    version: [">=1.0.0", "<1.1.0"]
```

Additionally, the `package-lock.yml` will also have to be upgraded. To do so, delete both the `package-lock.yml` and the `dbt_packages/` directory, before running `dbt deps` again which will recreate them both again.

If new package versions introduce new parse or compile errors, check the package's release notes, in case there's breaking changes that have to be accommodated.


If a latest version still throws an error at parse time but is already on the latest version, `dbt-autofix deprecations` has a `--include-packages` flag that may help resolve the issue.

## CHALLENGES

Often upgrading packages isn't as simple as increasing the version number.

There's often changes to the project that are needed. To learn more about required changes check the release notes for the package on GitHub. The url format for package release notes is
```
https://github.com/{package_owner}/{package_name}/releases
```

For the the latest Fusion compatible releases of Fivetran packages, the source (`_source`) packages have deprecated and rolled into the main packages.

The result is that there may be reference in `dbt_project.yml` to `*_source` package models, sources, and variables that have to be adjusted.

If the user project has an explicit, non-transitive dependency on a Fivetran package whose name ends in `_source`, know that the dependency has to be changed to be the main package

e.g. `fivetran/microsoft_ads_source` no longer exists as it's own package, it lives within `fivetran/microsoft_ads` now.

After doing so, the models from the package not originating from the source package need to be explicitly disabled.