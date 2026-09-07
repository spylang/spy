## [Update: 31/May/2026)
### Summary:
- it failed at module level

### Assumption:
- Environment may not store `x` if `x += _`.
- Parser doesn't parse `x` as varaible properly.

### Things to verify:
- How about global module level?
- Does this occur only on local module level?
- How about module in another files?