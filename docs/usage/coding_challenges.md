# Using SWE-agent for coding challenges

!!! abstract "Overview"
    It is easy to use SWE-agent to do more than just software engineering.
    For example, you can tell SWE-agent to work on leetcode or humaneval-style problems.

    Required reading:
    Please first skim [hello world](hello_world.md) and [command line basics](cl_tutorial.md) to get familiar with the basics of SWE-agent.


Let's start with a new problem statement. For this, put the problem you want to solve in a markdown file `problem.md`, for example:

<details>
<summary>Example leetcode challenge</summary>

This is the <a href="https://leetcode.com/problems/first-missing-positive/">first missing positive</a> challenge.

```markdown
--8<-- "docs/usage/leetcode_example.md"
```

</details>

Second, we need to specify a repository wherein SWE-agent will work.
Here, we can simply create an empty folder (outside of the SWE-agent repository), and add a `main.py` file

```bash
mkdir empty
git init
touch main.py
echo "*.pyc" > .gitignore  # to avoid binary files in patches
```

and potentially populate it with the problem stub

```python
from typing import List


class Solution:
    def firstMissingPositive(self, nums: List[int]) -> int:
```

!!! tip
    If some imports (like `List`) are missing in the problem stub (like they oftentimes do
    in leetcode) , SWE-agent will figure out how to add them. However, it might take an
    additional step, so it's best to directly specify them.

Make sure to commit all changes to the repository:

```bash
git add . && git commit -m "Add problem stub"
```

Now, we can let SWE-agent solve the problem:

```bash
sweagent run \
    --config config/coding_challenge.yaml \
    --problem_statement.path=problem.md \
    --env.repo.path=/path/to/empty \
    --agent.model.name=gpt-4o \
    --agent.model.per_instance_cost_limit 3.0 \
    --actions.apply_patch_locally=True
```

<details>
<summary>Output</summary>

```
--8<-- "docs/usage/coding_challenge_output.log"
```

</details>

SWE-agent will typically conclude with a message like

```
INFO     Trajectory saved to trajectories/fuchur/azure-gpt4__problem__coding_challenge__t-0.00__p-0.95__c-3.00__install-1/26d111.traj
INFO     Saved predictions to
         trajectories/fuchur/azure-gpt4__problem__coding_challenge__t-0.00__p-0.95__c-3.00__install-1/all_preds.jsonl
╭──────────────────────────── 🎉 Submission successful 🎉 ────────────────────────────╮
│ SWE-agent has produced a patch that it believes will solve the issue you submitted! │
│ Use the code snippet below to inspect or apply it!                                  │
╰─────────────────────────────────────────────────────────────────────────────────────╯

 # The patch has been saved to your local filesystem at:
 PATCH_FILE_PATH='/Users/fuchur/Documents/24/git_sync/SWE-agent/trajectories/fuchur/azure-gpt4__problem__coding_challenge__t-0.00__p-0
 5__c-3.00__install-1/patches/26d111.patch'
 # Inspect it:
 cat "${PATCH_FILE_PATH}"
 # Apply it to a local repository:
 cd <your local repo root>
 git apply "${PATCH_FILE_PATH}"
```

This informs you of the location of the [trajectory](trajectories.md) and of the patch file that contains the solution.

In our case, this looks like this:


<details>
<summary>Patch (solution)</summary>

```patch
diff --git a/main.py b/main.py
index 1e7f08f..beabaa7 100644
--- a/main.py
+++ b/main.py
@@ -2,4 +2,37 @@ from typing import List


 class Solution:
-    def firstMissingPositive(self, nums: List[int]) -> int:
+        # Implementation of the function to find the smallest missing positive integer
+        def firstMissingPositive(self, nums: List[int]) -> int:
+            n = len(nums)
+            # Mark numbers (num < 0) and (num > n) with a special marker number (n+1)
+            # We can ignore those because if missing number is in the range (1, n+1)
+            # it must be in the array
+            for i in range(n):
+                if nums[i] <= 0 or nums[i] > n:
+                    nums[i] = n + 1
+
+            # Use index as a hash key and number sign as a presence detector
+            # For example, if nums[1] is negative that means that number `1` is present in the array
+            for i in range(n):
+                num = abs(nums[i])
+                if num <= n:
+                    nums[num - 1] = -abs(nums[num - 1])
+
+            # Now the index of the first positive number is equal to the smallest missing positive number
+            for i in range(n):
+                if nums[i] > 0:
+                    return i + 1
+
+            # If no positive numbers were found, the smallest missing positive is n+1
+            return n + 1
+# Adding test cases to verify the implementation of firstMissingPositive
+if __name__ == "__main__":
+    sol = Solution()
+    # Test case 1
+    assert sol.firstMissingPositive([1, 2, 0]) == 3, "Test case 1 failed"
+    # Test case 2
+    assert sol.firstMissingPositive([3, 4, -1, 1]) == 2, "Test case 2 failed"
+    # Test case 3
+    assert sol.firstMissingPositive([7, 8, 9, 11, 12]) == 1, "Test case 3 failed"
+    print("All test cases passed successfully.")
```
</details>

Because of the `--apply_patch_locally` flag, the patch has also already been applied to the repository,
so you can also retrieve the final solution from there.

### Improving SWE-agent for coding challenges

By default, the demonstration trajectory the agent uses while solving a coding challenge is one in which it needs to solve a small bug in a short piece of code (from the HumanEvalFix dataset). Since that process is not too similar to solving a coding challenge, performance would probably substantially improve if the agent was given a demonstration trajectory in which it has to solve an actual programming challenge. To learn how to do that, read [this](../config/demonstrations.md).
