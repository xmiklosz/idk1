#include "ram.h"
#include <stddef.h>
#include <string.h>

static void *ram_memory = NULL;
static tRam *ram_struct = NULL;
static uint16_t num_frames = 0;

// Helper function to check if a number is a power of 2
static int is_power_of_2(uint16_t n) {
    return n != 0 && (n & (n - 1)) == 0;
}

// Helper function to get/set bitmap bits
static int get_bitmap_bit(uint16_t frame_id) {
    uint16_t byte_index = frame_id / 8;
    uint8_t bit_index = frame_id % 8;
    return (ram_struct->bitmap[byte_index] >> bit_index) & 1;
}

static void set_bitmap_bit(uint16_t frame_id, int value) {
    uint16_t byte_index = frame_id / 8;
    uint8_t bit_index = frame_id % 8;
    if (value) {
        ram_struct->bitmap[byte_index] |= (1 << bit_index);
    } else {
        ram_struct->bitmap[byte_index] &= ~(1 << bit_index);
    }
}

int init_ram(void *memory, uint16_t size, uint8_t page_size) {
    // Validate parameters
    if (memory == NULL) {
        return -3;
    }

    if (size == 0 || !is_power_of_2(size)) {
        return -1;
    }

    if (page_size == 0 || !is_power_of_2(page_size) || page_size > size) {
        return -2;
    }

    // Check if memory is zeroed
    uint8_t *mem_bytes = (uint8_t *)memory;
    for (uint16_t i = 0; i < size; i++) {
        if (mem_bytes[i] != 0) {
            return -3;
        }
    }

    // Calculate number of frames
    num_frames = size / page_size;

    // Calculate space needed for tRam and bitmap
    uint16_t bitmap_size = (num_frames + 7) / 8;  // Round up to nearest byte
    uint16_t metadata_size = sizeof(tRam) + bitmap_size;
    uint16_t metadata_frames = (metadata_size + page_size - 1) / page_size;  // Round up

    if (metadata_frames >= num_frames) {
        return -4;
    }

    // Initialize RAM structure
    ram_memory = memory;
    ram_struct = (tRam *)memory;
    ram_struct->size = size;
    ram_struct->page_size = page_size;
    ram_struct->bitmap = (uint8_t *)((uint8_t *)memory + sizeof(tRam));

    // Mark metadata frames as allocated
    for (uint16_t i = 0; i < metadata_frames; i++) {
        set_bitmap_bit(i, 1);
    }

    return num_frames;
}

void destroy_ram() {
    if (ram_memory != NULL) {
        // Zero out the RAM
        memset(ram_memory, 0, ram_struct->size);
        ram_memory = NULL;
        ram_struct = NULL;
        num_frames = 0;
    }
}

int falloc(uint16_t *frame_id, uint16_t number) {
    if (ram_struct == NULL) {
        return -1;
    }

    if (frame_id == NULL || number == 0) {
        return -2;
    }

    // First-fit algorithm: find consecutive free frames
    uint16_t consecutive_free = 0;
    uint16_t start_frame = 0;

    for (uint16_t i = 0; i < num_frames; i++) {
        if (get_bitmap_bit(i) == 0) {
            if (consecutive_free == 0) {
                start_frame = i;
            }
            consecutive_free++;

            if (consecutive_free == number) {
                // Found enough consecutive frames
                *frame_id = start_frame;

                // Mark frames as allocated
                for (uint16_t j = 0; j < number; j++) {
                    set_bitmap_bit(start_frame + j, 1);
                }

                return 0;
            }
        } else {
            consecutive_free = 0;
        }
    }

    // Not enough consecutive space
    return -1;
}

void ffree(uint16_t frame_id, uint16_t number) {
    if (ram_struct == NULL) {
        return;
    }

    if (frame_id >= num_frames) {
        return;
    }

    // Free the frames
    for (uint16_t i = 0; i < number && (frame_id + i) < num_frames; i++) {
        set_bitmap_bit(frame_id + i, 0);

        // Zero out the frame content
        uint8_t *frame_start = (uint8_t *)ram_memory + (frame_id + i) * ram_struct->page_size;
        memset(frame_start, 0, ram_struct->page_size);
    }
}

const tRam *get_ram_state() {
    return ram_struct;
}
