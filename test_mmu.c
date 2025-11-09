#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#include "ram.h"
#include "task.h"
#include "mmu.h"
#include "pager.h"

#define RAM_SIZE 512
#define PAGE_SIZE 64
#define TEST_PASSED printf("✓ ")
#define TEST_FAILED printf("✗ ")

void test_ram_initialization() {
    printf("Testing RAM initialization...\n");

    // Test 1: Initialize RAM with valid parameters
    uint8_t memory[RAM_SIZE] = {0};
    int num_frames = init_ram(memory, RAM_SIZE, PAGE_SIZE);
    assert(num_frames > 0);
    printf("  Number of frames: %d\n", num_frames);
    TEST_PASSED; printf("RAM initialized successfully\n");

    // Test 2: Check RAM state
    const tRam *ram = get_ram_state();
    assert(ram != NULL);
    assert(ram->size == RAM_SIZE);
    assert(ram->page_size == PAGE_SIZE);
    TEST_PASSED; printf("RAM state is correct\n");

    destroy_ram();
    TEST_PASSED; printf("RAM destroyed successfully\n");
}

void test_frame_allocation() {
    printf("\nTesting frame allocation...\n");

    uint8_t memory[RAM_SIZE] = {0};
    init_ram(memory, RAM_SIZE, PAGE_SIZE);

    // Test 1: Allocate single frame
    uint16_t frame_id;
    int result = falloc(&frame_id, 1);
    assert(result == 0);
    TEST_PASSED; printf("Single frame allocated (ID: %d)\n", frame_id);

    // Test 2: Allocate multiple consecutive frames
    uint16_t frame_id2;
    result = falloc(&frame_id2, 2);
    assert(result == 0);
    TEST_PASSED; printf("Multiple frames allocated (ID: %d)\n", frame_id2);

    // Test 3: Free frames
    ffree(frame_id, 1);
    TEST_PASSED; printf("Frame freed successfully\n");

    destroy_ram();
}

void test_task_management() {
    printf("\nTesting task management...\n");

    uint8_t memory[RAM_SIZE] = {0};
    init_ram(memory, RAM_SIZE, PAGE_SIZE);

    // Initialize task manager
    int result = init_taskMgr();
    assert(result == 0);
    TEST_PASSED; printf("Task manager initialized\n");

    // Create a task
    tPageTableEntry page_table[PAGE_TABLE_SIZE];
    memset(page_table, 0, sizeof(page_table));

    // Set up permissions for pages
    for (int i = 0; i < PAGE_TABLE_SIZE; i++) {
        page_table[i].r = 1;
        page_table[i].w = 1;
        page_table[i].x = 1;
    }

    uint8_t address_space[RAM_SIZE] = {0};
    int pid = create_task(page_table, 3, address_space);
    assert(pid > 0);
    TEST_PASSED; printf("Task created (PID: %d)\n", pid);

    // Get task structure
    tTaskStruct *task = get_task_struct(pid);
    assert(task != NULL);
    assert(task->pid == pid);
    TEST_PASSED; printf("Task structure retrieved\n");

    // Destroy task
    result = destroy_task(pid);
    assert(result == 0);
    TEST_PASSED; printf("Task destroyed\n");

    destroy_taskMgr();
    destroy_ram();
}

void test_mmu_operations() {
    printf("\nTesting MMU operations...\n");

    uint8_t memory[RAM_SIZE] = {0};
    init_ram(memory, RAM_SIZE, PAGE_SIZE);
    init_taskMgr();

    // Create a task
    tPageTableEntry page_table[PAGE_TABLE_SIZE];
    memset(page_table, 0, sizeof(page_table));

    for (int i = 0; i < PAGE_TABLE_SIZE; i++) {
        page_table[i].r = 1;
        page_table[i].w = 1;
        page_table[i].x = 1;
    }

    uint8_t address_space[RAM_SIZE] = {0};
    int pid = create_task(page_table, 0, address_space);

    tTaskStruct *task = get_task_struct(pid);
    set_page_table(task->page_table);

    // Test page fault handling
    printf("  Testing page fault...\n");
    int result = page_fault(pid, 0);
    assert(result == 0);
    TEST_PASSED; printf("Page fault handled successfully\n");

    // Test store_data
    printf("  Testing store_data...\n");
    result = store_data(10, 0x42);
    assert(result == 0);
    TEST_PASSED; printf("Data stored successfully\n");

    // Test load_data
    printf("  Testing load_data...\n");
    uint8_t data;
    result = load_data(10, &data);
    assert(result == 0);
    assert(data == 0x42);
    TEST_PASSED; printf("Data loaded successfully (value: 0x%02X)\n", data);

    // Test fetch_instruction
    printf("  Testing fetch_instruction...\n");
    result = fetch_instruction(10, &data);
    assert(result == 0);
    TEST_PASSED; printf("Instruction fetched successfully\n");

    destroy_task(pid);
    destroy_taskMgr();
    destroy_ram();
}

void test_page_replacement() {
    printf("\nTesting page replacement (NRU algorithm)...\n");

    uint8_t memory[RAM_SIZE] = {0};
    init_ram(memory, RAM_SIZE, PAGE_SIZE);
    init_taskMgr();

    // Create a task with limited frames
    tPageTableEntry page_table[PAGE_TABLE_SIZE];
    memset(page_table, 0, sizeof(page_table));

    for (int i = 0; i < PAGE_TABLE_SIZE; i++) {
        page_table[i].r = 1;
        page_table[i].w = 1;
        page_table[i].x = 1;
    }

    uint8_t address_space[RAM_SIZE] = {0};
    // Initialize address space with some data
    for (int i = 0; i < RAM_SIZE; i++) {
        address_space[i] = i & 0xFF;
    }

    int pid = create_task(page_table, 2, address_space);  // Max 2 frames
    tTaskStruct *task = get_task_struct(pid);
    set_page_table(task->page_table);

    // Load first page
    printf("  Loading page 0...\n");
    int result = page_fault(pid, 0);
    assert(result == 0);
    TEST_PASSED; printf("Page 0 loaded\n");

    // Load second page
    printf("  Loading page 1...\n");
    result = page_fault(pid, PAGE_SIZE);
    assert(result == 0);
    TEST_PASSED; printf("Page 1 loaded\n");

    // Try to load third page (should trigger page replacement)
    printf("  Loading page 2 (should trigger replacement)...\n");
    result = page_fault(pid, PAGE_SIZE * 2);
    assert(result == 0);
    TEST_PASSED; printf("Page 2 loaded (page replacement occurred)\n");

    destroy_task(pid);
    destroy_taskMgr();
    destroy_ram();
}

void test_access_violations() {
    printf("\nTesting access violations...\n");

    uint8_t memory[RAM_SIZE] = {0};
    init_ram(memory, RAM_SIZE, PAGE_SIZE);
    init_taskMgr();

    // Create a task with restricted permissions
    tPageTableEntry page_table[PAGE_TABLE_SIZE];
    memset(page_table, 0, sizeof(page_table));

    // Page 0: read-only
    page_table[0].r = 1;
    page_table[0].w = 0;
    page_table[0].x = 0;

    // Page 1: no access
    page_table[1].r = 0;
    page_table[1].w = 0;
    page_table[1].x = 0;

    uint8_t address_space[RAM_SIZE] = {0};
    int pid = create_task(page_table, 0, address_space);
    tTaskStruct *task = get_task_struct(pid);
    set_page_table(task->page_table);

    // Load page 0
    page_fault(pid, 0);

    // Test write to read-only page
    printf("  Testing write to read-only page...\n");
    int result = store_data(10, 0x42);
    assert(result == -3);  // Access violation
    TEST_PASSED; printf("Write to read-only page correctly denied\n");

    // Test access to inaccessible page
    printf("  Testing access to inaccessible page...\n");
    uint8_t data;
    result = load_data(PAGE_SIZE, &data);
    assert(result == -2);  // Segmentation fault
    TEST_PASSED; printf("Access to inaccessible page correctly denied\n");

    destroy_task(pid);
    destroy_taskMgr();
    destroy_ram();
}

int main() {
    printf("=== MMU System Test Suite ===\n\n");

    test_ram_initialization();
    test_frame_allocation();
    test_task_management();
    test_mmu_operations();
    test_page_replacement();
    test_access_violations();

    printf("\n=== All tests passed! ===\n");
    return 0;
}
