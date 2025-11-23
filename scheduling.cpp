#include <iostream>
#include <vector>
#include <algorithm>

using namespace std;

// Simple job structure
struct JobData {
    int number;
    int deadline;
    int profit;
};

// Sort by profit (highest first)
bool sortByProfit(const JobData &a, const JobData &b) {
    return a.profit > b.profit;
}

// Check if a sequence of jobs is feasible
// Feasible means: when sorted by deadline, each job at position p has deadline >= p
bool checkFeasible(vector<JobData> sequence) {
    // Sort by deadline first
    sort(sequence.begin(), sequence.end(), [](const JobData &a, const JobData &b) {
        return a.deadline < b.deadline;
    });

    // Check if each job can meet its deadline
    for (size_t position = 0; position < sequence.size(); position++) {
        // Position is 0-indexed, but time slots are 1-indexed
        int timeSlot = position + 1;
        if (timeSlot > sequence[position].deadline) {
            return false;  // Job would miss its deadline
        }
    }

    return true;
}

// Main scheduling algorithm - Algorithm 4.4 from textbook
void schedule(int n, const int deadlines[], const int profits[],
              vector<int> &finalSequence, int &totalProfit) {

    // Create array of jobs
    vector<JobData> jobs(n);
    for (int i = 0; i < n; i++) {
        jobs[i].number = i + 1;
        jobs[i].deadline = deadlines[i];
        jobs[i].profit = profits[i];
    }

    // Sort jobs by profit (descending) as per algorithm requirement
    sort(jobs.begin(), jobs.end(), sortByProfit);

    // Algorithm 4.4 implementation
    // J starts with first job
    vector<JobData> J;
    J.push_back(jobs[0]);

    // Try adding each remaining job
    for (int i = 1; i < n; i++) {
        // Create K = J with job i added
        vector<JobData> K = J;
        K.push_back(jobs[i]);

        // Check if K is feasible
        if (checkFeasible(K)) {
            // Accept the new job
            J = K;
        }
        // Otherwise reject it (J stays unchanged)
    }

    // Sort final result by deadline for execution order
    sort(J.begin(), J.end(), [](const JobData &a, const JobData &b) {
        return a.deadline < b.deadline;
    });

    // Convert to job numbers and calculate total profit
    finalSequence.clear();
    totalProfit = 0;
    for (const auto &job : J) {
        finalSequence.push_back(job.number);
        totalProfit += job.profit;
    }
}

int main() {
    // Test with Table 1.1 from assignment
    const int n = 7;
    int deadlines[] = {2, 4, 3, 2, 3, 1, 1};
    int profits[] = {40, 15, 60, 20, 10, 45, 55};

    vector<int> result;
    int totalProfit;

    cout << "==========================================" << endl;
    cout << "   SCHEDULING WITH DEADLINES" << endl;
    cout << "   Algorithm 4.4 - Basic Greedy Approach" << endl;
    cout << "   AZA 2025/26 Assignment - PART 1" << endl;
    cout << "==========================================" << endl << endl;

    // Show input (Table 1.1)
    cout << "Input Jobs (Table 1.1):" << endl;
    cout << "Job | Deadline | Profit" << endl;
    cout << "----+----------+-------" << endl;
    for (int i = 0; i < n; i++) {
        cout << " " << (i + 1) << "  |    " << deadlines[i]
             << "     |   " << profits[i] << endl;
    }
    cout << endl;

    // Run algorithm
    schedule(n, deadlines, profits, result, totalProfit);

    // Display schedule
    cout << "Optimal Schedule:" << endl;
    cout << "Time | Job | Profit" << endl;
    cout << "-----+-----+-------" << endl;

    for (size_t time = 0; time < result.size(); time++) {
        int jobNum = result[time];
        int jobProfit = profits[jobNum - 1];

        cout << "  " << (time + 1) << "  |  " << jobNum << "  |   "
             << jobProfit << endl;
    }

    cout << "-----+-----+-------" << endl;
    cout << "Total Profit: " << totalProfit << endl << endl;

    cout << "Job Sequence: [";
    for (size_t i = 0; i < result.size(); i++) {
        cout << result[i];
        if (i < result.size() - 1) cout << ", ";
    }
    cout << "]" << endl << endl;

    // Complexity analysis
    cout << "==========================================" << endl;
    cout << "Algorithm Complexity Analysis:" << endl;
    cout << "==========================================" << endl;
    cout << "- Sorting jobs by profit: O(n log n)" << endl;
    cout << "- Main loop: n iterations" << endl;
    cout << "- Feasibility check per iteration: O(n log n)" << endl;
    cout << "  (sorting + linear check)" << endl;
    cout << "- Overall Time Complexity: O(n² log n)" << endl;
    cout << "- Space Complexity: O(n)" << endl << endl;

    cout << "Algorithm Steps:" << endl;
    cout << "1. Sort all jobs by profit (descending)" << endl;
    cout << "2. Start with highest profit job" << endl;
    cout << "3. For each remaining job:" << endl;
    cout << "   - Try adding it to current schedule" << endl;
    cout << "   - Check if still feasible (all deadlines met)" << endl;
    cout << "   - Keep it if feasible, reject otherwise" << endl;
    cout << "4. Return the feasible schedule with max profit" << endl;

    return 0;
}
