#include "mmu.h"
#include "ram.h"
#include <stddef.h>

static tPageTableEntry *current_page_table = NULL;

void set_page_table(tPageTableEntry *page_table) {
    current_page_table = page_table;
}

int get_physical_address(uint16_t virtual_address, uint16_t *physical_address) {
    if (physical_address == NULL) {
        return -3;
    }

    const tRam *ram = get_ram_state();
    if (ram == NULL) {
        return -5;
    }

    if (current_page_table == NULL) {
        return -4;
    }

    // Calculate page number and offset
    uint8_t page_size = ram->page_size;
    uint8_t page_bits = 0;
    uint8_t temp = page_size;
    while (temp > 1) {
        page_bits++;
        temp >>= 1;
    }

    uint8_t page_number = virtual_address >> page_bits;
    uint16_t offset = virtual_address & (page_size - 1);

    // Check if page number is valid
    if (page_number >= PAGE_TABLE_SIZE) {
        return -2;  // Segmentation fault
    }

    tPageTableEntry *entry = &current_page_table[page_number];

    // Check if page is present
    if (entry->p_bit == 0) {
        return -1;  // Page fault
    }

    // Calculate physical address
    *physical_address = entry->frame_id * page_size + offset;

    return 0;
}

int fetch_instruction(uint16_t virtual_address, uint8_t *data) {
    if (data == NULL) {
        return -3;
    }

    const tRam *ram = get_ram_state();
    if (ram == NULL) {
        return -4;
    }

    if (current_page_table == NULL) {
        return -4;
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
        return -2;  // Segmentation fault
    }

    tPageTableEntry *entry = &current_page_table[page_number];

    // Check if page is present FIRST
    if (entry->p_bit == 0) {
        return -1;  // Page fault
    }

    // Check if page is accessible
    if (entry->r == 0 && entry->w == 0 && entry->x == 0) {
        return -2;  // Segmentation fault
    }

    // Check execute permission
    if (entry->x == 0) {
        return -3;  // Access violation
    }

    // Get physical address
    uint16_t physical_address;
    int result = get_physical_address(virtual_address, &physical_address);
    if (result != 0) {
        return result;
    }

    // Read data from RAM
    uint8_t *ram_base = (uint8_t *)ram;
    *data = ram_base[physical_address];

    // Set referenced bit
    entry->r_bit = 1;

    return 0;
}

int load_data(uint16_t virtual_address, uint8_t *data) {
    if (data == NULL) {
        return -3;
    }

    const tRam *ram = get_ram_state();
    if (ram == NULL) {
        return -4;
    }

    if (current_page_table == NULL) {
        return -4;
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
        return -2;  // Segmentation fault
    }

    tPageTableEntry *entry = &current_page_table[page_number];

    // Check if page is present FIRST
    if (entry->p_bit == 0) {
        return -1;  // Page fault
    }

    // Check if page is accessible
    if (entry->r == 0 && entry->w == 0 && entry->x == 0) {
        return -2;  // Segmentation fault
    }

    // Check read permission
    if (entry->r == 0) {
        return -3;  // Access violation
    }

    // Get physical address
    uint16_t physical_address;
    int result = get_physical_address(virtual_address, &physical_address);
    if (result != 0) {
        return result;
    }

    // Read data from RAM
    uint8_t *ram_base = (uint8_t *)ram;
    *data = ram_base[physical_address];

    // Set referenced bit
    entry->r_bit = 1;

    return 0;
}

int store_data(uint16_t virtual_address, uint8_t data) {
    const tRam *ram = get_ram_state();
    if (ram == NULL) {
        return -4;
    }

    if (current_page_table == NULL) {
        return -4;
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
        return -2;  // Segmentation fault
    }

    tPageTableEntry *entry = &current_page_table[page_number];

    // Check if page is present FIRST
    if (entry->p_bit == 0) {
        return -1;  // Page fault
    }

    // Check if page is accessible
    if (entry->r == 0 && entry->w == 0 && entry->x == 0) {
        return -2;  // Segmentation fault
    }

    // Check write permission
    if (entry->w == 0) {
        return -3;  // Access violation
    }

    // Get physical address
    uint16_t physical_address;
    int result = get_physical_address(virtual_address, &physical_address);
    if (result != 0) {
        return result;
    }

    // Write data to RAM
    uint8_t *ram_base = (uint8_t *)ram;
    ram_base[physical_address] = data;

    // Set referenced and modified bits
    entry->r_bit = 1;
    entry->m_bit = 1;

    return 0;
}
