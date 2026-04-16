# LookML Generation — Multi-Hop Drill-Down Limitation

## Background

The user wants a 3-hop drill path: opportunities → accounts → regions → territories. This hits the Looker limitation where users can't drill below the grain declared in saved_query exports. The agent should surface this limitation before writing, and offer a drill-link hybrid pattern as an alternative.

## Expected Outcome

The agent should:
1. Detect the >2 join-hop scenario (opportunities → accounts → regions)
2. Explain the Looker drill-down limitation (can't drill below export grain)
3. Ask whether the user wants a drill link to a native LookML explore for detail
4. If yes: offer a `link:` field on the relevant dimension

## Grading Criteria

- [ ] multi_hop_detected: Agent identifies that the join graph has >2 hops
- [ ] drill_limitation_explained: Agent explains that Looker users cannot drill below the export grain
- [ ] drill_link_offered: Agent offers a drill link (`link:` field) as the recommended workaround
- [ ] acknowledgement_before_write: Agent asks for user input before generating the deep-drill explore
- [ ] explore_still_generated: Despite the warning, a valid LookML explore IS generated (just with the limitation noted)
- [ ] join_structure_correct: The generated explore has `join: accounts` and `join: regions` with `many_to_one`
