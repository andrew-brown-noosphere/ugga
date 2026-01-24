# UGA Course Scheduler - TODO

## Future Features

### Double Dawgs Support
UGA's Double Dawgs program allows students to pursue combined BS/MS pathways. We should support these in the degree planning system.

**Example pathways for Computer Science:**
- Computer Science BS / Artificial Intelligence MS
- Computer Science BS / Computer Science MS (non-thesis)
- Computer Science BS / Cybersecurity and Privacy MS (non-thesis)
- Computer Science BS / Journalism and Mass Communication MA (Emerging Media) (non-thesis)

**Implementation ideas:**
- [ ] Add `double_dawgs_pathways` field to Program model
- [ ] Show Double Dawgs badge on eligible programs
- [ ] Allow users to select a Double Dawgs pathway as their goal
- [ ] Display combined requirements (undergrad + grad courses)
- [ ] Show which undergrad courses count toward both degrees
- [ ] Link to official Double Dawgs info: https://doubledawgs.uga.edu/

---

## Known Limitations

- Sections not returned in course list API (only section_count) - need to fetch individual course for section details
- Some programs may have "General Electives" with 0 courses listed (these are open elective slots where any course can be used)
