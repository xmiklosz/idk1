#include "task.h"
#include "ram.h"
#include <stddef.h>
#include <string.h>

static tTaskMgr *task_mgr = NULL;
static uint16_t task_mgr_frame_id = 0;
static int next_pid = 1;

int init_taskMgr() {
    const tRam *ram = get_ram_state();
    if (ram == NULL) {
        return -1;
    }

    // Calculate frames needed for tTaskMgr
    uint16_t frames_needed = (sizeof(tTaskMgr) + ram->page_size - 1) / ram->page_size;

    // Allocate frames for task manager
    if (falloc(&task_mgr_frame_id, frames_needed) != 0) {
        return -1;
    }

    // Get pointer to task manager in RAM
    uint8_t *ram_base = (uint8_t *)ram;
    ram_base = ram_base - sizeof(tRam) - ((ram->size / ram->page_size + 7) / 8);
    task_mgr = (tTaskMgr *)((uint8_t *)ram_base + task_mgr_frame_id * ram->page_size);

    // Initialize all tasks as free (PID = -1)
    for (int i = 0; i < TASK_TABLE_SIZE; i++) {
        task_mgr->tasks[i].pid = -1;
        task_mgr->tasks[i].max_frames = 0;
        task_mgr->tasks[i].address_space = NULL;
        memset(task_mgr->tasks[i].page_table, 0, sizeof(tPageTableEntry) * PAGE_TABLE_SIZE);
    }

    return 0;
}

void destroy_taskMgr() {
    if (task_mgr == NULL) {
        return;
    }

    // Destroy all tasks first
    for (int i = 0; i < TASK_TABLE_SIZE; i++) {
        if (task_mgr->tasks[i].pid != -1) {
            destroy_task(task_mgr->tasks[i].pid);
        }
    }

    // Free task manager frames
    const tRam *ram = get_ram_state();
    if (ram != NULL) {
        uint16_t frames_needed = (sizeof(tTaskMgr) + ram->page_size - 1) / ram->page_size;
        ffree(task_mgr_frame_id, frames_needed);
    }

    task_mgr = NULL;
}

int create_task(const tPageTableEntry *page_table, uint8_t max_frames, void *address_space) {
    if (task_mgr == NULL) {
        return -3;
    }

    if (page_table == NULL) {
        return -2;
    }

    // Find a free task slot
    int free_slot = -1;
    for (int i = 0; i < TASK_TABLE_SIZE; i++) {
        if (task_mgr->tasks[i].pid == -1) {
            free_slot = i;
            break;
        }
    }

    if (free_slot == -1) {
        return -1;  // No free slots
    }

    // Assign PID
    int new_pid = next_pid++;

    // Initialize task
    task_mgr->tasks[free_slot].pid = new_pid;
    task_mgr->tasks[free_slot].max_frames = max_frames;
    task_mgr->tasks[free_slot].address_space = address_space;

    // Copy page table (all pages initially not present)
    for (int i = 0; i < PAGE_TABLE_SIZE; i++) {
        task_mgr->tasks[free_slot].page_table[i] = page_table[i];
        task_mgr->tasks[free_slot].page_table[i].p_bit = 0;  // Not present initially
        task_mgr->tasks[free_slot].page_table[i].r_bit = 0;
        task_mgr->tasks[free_slot].page_table[i].m_bit = 0;
        // frame_id is preserved from page_table[i]
    }

    return new_pid;
}

int destroy_task(int pid) {
    if (task_mgr == NULL) {
        return -1;
    }

    // Find the task
    tTaskStruct *task = NULL;
    for (int i = 0; i < TASK_TABLE_SIZE; i++) {
        if (task_mgr->tasks[i].pid == pid) {
            task = &task_mgr->tasks[i];
            break;
        }
    }

    if (task == NULL) {
        return -1;
    }

    // Free all frames used by the task
    for (int i = 0; i < PAGE_TABLE_SIZE; i++) {
        if (task->page_table[i].p_bit) {
            ffree(task->page_table[i].frame_id, 1);
        }
    }

    // Mark task as free
    task->pid = -1;
    task->max_frames = 0;
    task->address_space = NULL;
    memset(task->page_table, 0, sizeof(tPageTableEntry) * PAGE_TABLE_SIZE);

    return 0;
}

const tTaskMgr *get_task_mgr() {
    return task_mgr;
}

tTaskStruct *get_task_struct(int pid) {
    if (task_mgr == NULL) {
        return NULL;
    }

    for (int i = 0; i < TASK_TABLE_SIZE; i++) {
        if (task_mgr->tasks[i].pid == pid) {
            return &task_mgr->tasks[i];
        }
    }

    return NULL;
}
