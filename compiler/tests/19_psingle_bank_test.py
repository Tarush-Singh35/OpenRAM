#!/usr/bin/env python3
# See LICENSE for licensing information.
#
# Copyright (c) 2016-2019 Regents of the University of California and The Board
# of Regents for the Oklahoma Agricultural and Mechanical College
# (acting for and on behalf of Oklahoma State University)
# All rights reserved.
#
import unittest
from testutils import *
import sys,os
sys.path.append(os.getenv("OPENRAM_HOME"))
import globals
from globals import OPTS
from sram_factory import factory
import debug

#@unittest.skip("SKIPPING 19_psingle_bank_test")
class psingle_bank_test(openram_test):

    def runTest(self):
        globals.init_openram("config_{0}".format(OPTS.tech_name))
        from sram_config import sram_config
        
        OPTS.bitcell = "pbitcell"
        OPTS.replica_bitcell="replica_pbitcell"
        OPTS.dummy_bitcell="dummy_pbitcell"
        
        OPTS.num_rw_ports = 1
        OPTS.num_w_ports = 0
        OPTS.num_r_ports = 0
        
        c = sram_config(word_size=4,
                        num_words=16)
        
        c.words_per_row=1
        factory.reset()
        c.recompute_sizes()
        debug.info(1, "No column mux")
        a = factory.create(module_type="bank", sram_config=c)
        self.local_check(a)
        
        c.num_words=32
        c.words_per_row=2
        factory.reset()
        c.recompute_sizes()
        debug.info(1, "Two way column mux")
        a = factory.create(module_type="bank", sram_config=c)
        self.local_check(a)
        
        c.num_words=64
        c.words_per_row=4
        factory.reset()
        c.recompute_sizes()
        debug.info(1, "Four way column mux")
        a = factory.create(module_type="bank", sram_config=c)
        self.local_check(a)
        
        c.word_size=2
        c.num_words=128
        c.words_per_row=8
        factory.reset()
        c.recompute_sizes()
        debug.info(1, "Four way column mux")
        a = factory.create(module_type="bank", sram_config=c)
        self.local_check(a)
        
        globals.end_openram()
        
# run the test from the command line
if __name__ == "__main__":
    (OPTS, args) = globals.parse_args()
    del sys.argv[1:]
    header(__file__, OPTS.tech_name)
    unittest.main(testRunner=debugTestRunner())
