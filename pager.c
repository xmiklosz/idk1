#include "pager.h"
#include "task.h"
#include "ram.h"
#include <stddef.h>
#include <string.h>

// Helper function to write a page to task's address space
static void write_page_to_address_space(tTaskStruct *task, uint8_t page_num) {
    const tRam *ram = get_ram_state();
    if (ram == NULL || task == NULL) {
        return;
    }

    tPageTableEntry *entry = &task->page_table[page_num];
    if (!entry->p_bit) {
        return;
    }

    // Get frame data from RAM
    uint8_t *ram_base = (uint8_t *)ram;
    ram_base = ram_base - sizeof(tRam) - ((ram->size / ram->page_size + 7) / 8);
    uint8_t *frame_data = ram_base + entry->frame_id * ram->page_size;

    // Write to address space (simulate disk write)
    if (task->address_space != NULL) {
        uint8_t *address_space = (uint8_t *)task->address_space;
        memcpy(address_space + page_num * ram->page_size, frame_data, ram->page_size);
    }
}

// Helper function to read a page from task's address space
static void read_page_from_address_space(tTaskStruct *task, uint8_t page_num, uint16_t frame_id) {
    const tRam *ram = get_ram_state();
    if (ram == NULL || task == NULL) {
        return;
    }

    // Get frame location in RAM
    uint8_t *ram_base = (uint8_t *)ram;
    ram_base = ram_base - sizeof(tRam) - ((ram->size / ram->page_size + 7) / 8);
    uint8_t *frame_data = ram_base + frame_id * ram->page_size;

    // Read from address space (simulate disk read)
    if (task->address_space != NULL) {
        uint8_t *address_space = (uint8_t *)task->address_space;
        memcpy(frame_data, address_space + page_num * ram->page_size, ram->page_size);
    } else {
        // If no address space, zero the frame
        memset(frame_data, 0, ram->page_size);
    }
}

// NRU page replacement algorithm
static int select_victim_page(tTaskStruct *task) {
    // NRU classes:
    // Class 0: r=0, m=0 (not referenced, not modified)
    // Class 1: r=0, m=1 (not referenced, modified)
    // Class 2: r=1, m=0 (referenced, not modified)
    // Class 3: r=1, m=1 (referenced, modified)

    int victim = -1;
    int victim_class = 4;  // Start with invalid class

    for (int i = 0; i < PAGE_TABLE_SIZE; i++) {
        if (task->page_table[i].p_bit) {
            int page_class = (task->page_table[i].r_bit << 1) | task->page_table[i].m_bit;

            if (page_class < victim_class) {
                victim_class = page_class;
                victim = i;

                // If we found a class 0 page, use it immediately
                if (page_class == 0) {
                    break;
                }
            }
        }
    }

    return victim;
}

int page_fault(int pid, uint16_t virtual_address) {
    tTaskStruct *task = get_task_struct(pid);
    if (task == NULL) {
        return -1;  // Task not found
    }

    const tRam *ram = get_ram_state();
    if (ram == NULL) {
        return -3;  // Out of resources
    }

    // Calculate page number
    uint8_t page_size = ram->page_size;
    uint8_t page_bits = 0;
    uint8_t temp = page_size;
    while (temp > 1) {
        page_bits++;
        temp >>= 1;
    }

    uint8_t page_number = virtual_address >> page_bits;

    if (page_number >= PAGE_TABLE_SIZE) {
        return -4;  // Segmentation fault
    }

    tPageTableEntry *entry = &task->page_table[page_number];

    // Check if page is accessible
    if (entry->r == 0 && entry->w == 0 && entry->x == 0) {
        return -4;  // Segmentation fault
    }

    // Check if page is already present
    if (entry->p_bit) {
        return -2;  // Page already in RAM
    }

    // Write all modified pages to address space first
    for (int i = 0; i < PAGE_TABLE_SIZE; i++) {
        if (task->page_table[i].p_bit && task->page_table[i].m_bit) {
            write_page_to_address_space(task, i);
        }
    }

    // Count how many frames the task currently has
    int frames_in_use = 0;
    for (int i = 0; i < PAGE_TABLE_SIZE; i++) {
        if (task->page_table[i].p_bit) {
            frames_in_use++;
        }
    }

    // Check if we need to evict a page
    uint16_t new_frame_id;
    if (task->max_frames > 0 && frames_in_use >= task->max_frames) {
        // Need to evict a page using NRU algorithm
        int victim = select_victim_page(task);
        if (victim == -1) {
            return -3;  // No victim found (should not happen)
        }

        // Use the victim's frame
        new_frame_id = task->page_table[victim].frame_id;

        // Mark victim page as not present
        task->page_table[victim].p_bit = 0;
        task->page_table[victim].frame_id = 0;
    } else {
        // Try to allocate a new frame
        if (falloc(&new_frame_id, 1) != 0) {
            // No free frames available, need to evict
            if (frames_in_use == 0) {
                return -3;  // Out of resources
            }

            int victim = select_victim_page(task);
            if (victim == -1) {
                return -3;  // No victim found
            }

            // Use the victim's frame
            new_frame_id = task->page_table[victim].frame_id;

            // Mark victim page as not present
            task->page_table[victim].p_bit = 0;
            task->page_table[victim].frame_id = 0;
        }
    }

    // Load page content from address space
    read_page_from_address_space(task, page_number, new_frame_id);

    // Update page table entry
    entry->p_bit = 1;
    entry->frame_id = new_frame_id;

    // Clear r_bit and m_bit for all pages of the task
    for (int i = 0; i < PAGE_TABLE_SIZE; i++) {
        if (task->page_table[i].p_bit) {
            task->page_table[i].r_bit = 0;
            task->page_table[i].m_bit = 0;
        }
    }

    return 0;
}
