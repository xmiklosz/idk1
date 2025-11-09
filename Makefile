CC = gcc
CFLAGS = -Wall -Wextra -std=c99 -g
LDFLAGS = -lm

# Source files
SOURCES = ram.c task.c mmu.c pager.c
OBJECTS = $(SOURCES:.c=.o)
HEADERS = types.h ram.h task.h mmu.h pager.h

# Targets
LIB = libmmu.a
TEST = test_mmu

.PHONY: all clean test

all: $(LIB) $(TEST)

# Build static library
$(LIB): $(OBJECTS)
	ar rcs $@ $^

# Build test program
$(TEST): test_mmu.o $(LIB)
	$(CC) $(CFLAGS) -o $@ $^ $(LDFLAGS)

# Pattern rule for object files
%.o: %.c $(HEADERS)
	$(CC) $(CFLAGS) -c $< -o $@

# Run tests
test: $(TEST)
	./$(TEST)

clean:
	rm -f $(OBJECTS) test_mmu.o $(LIB) $(TEST)

# Dependencies
ram.o: ram.c ram.h
task.o: task.c task.h types.h ram.h
mmu.o: mmu.c mmu.h types.h ram.h
pager.o: pager.c pager.h task.h ram.h types.h
test_mmu.o: test_mmu.c ram.h task.h mmu.h pager.h types.h
